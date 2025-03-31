import os
import logging
import pathlib
from fastapi import FastAPI, Form, HTTPException, Depends, UploadFile, File, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from pydantic import BaseModel
from contextlib import asynccontextmanager
import json
import hashlib
from typing import List


# Define the path to the images & sqlite3 database
images = pathlib.Path(__file__).parent.resolve() / "images"
db = pathlib.Path(__file__).parent.resolve() / "db" / "mercari.sqlite3"


def get_db():
    if not db.exists():
        yield
    conn = sqlite3.connect(db) # データベースに接続
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    try:
        yield conn
    finally:
        conn.close()


# STEP 5-1: set up the database connection
def setup_database():
    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)

    # `items` テーブルを作成（なければ作成）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            image_name TEXT NOT NULL,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    """)
    conn.commit()
    conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_database()
    yield


app = FastAPI(lifespan=lifespan)

logger = logging.getLogger("uvicorn")
logger.level = logging.INFO
images = pathlib.Path(__file__).parent.resolve() / "images"
origins = [os.environ.get("FRONT_URL", "http://localhost:3000")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


def save_image(file: UploadFile) -> str:
    content = file.file.read()  # ← 画像のデータを全部読み込む（バイナリデータ(jpgとかtextじゃないデータ)）???
    hashed_name = hashlib.sha256(content).hexdigest()  # ハッシュ化??? hashed-valueが返るの？
    file_name = f"{hashed_name}.jpg"
    file_path = images / file_name

    with open(file_path, "wb") as f:  # wb = バイナリ書き込み
        f.write(content)
    return file_name


class HelloResponse(BaseModel):
    message: str


@app.get("/", response_model=HelloResponse)
def hello():
    return HelloResponse(**{"message": "Hello, world!"})

class Item(BaseModel):
    name: str
    category: str

class GetItemResponse(BaseModel):
    items: list[Item]

@app.get("/items", response_model=GetItemResponse)#デコレーター(FAST API)
def get_items(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT items.id, items.name, categories.name AS category, items.image_name FROM items JOIN categories ON items.category_id = categories.id")
    items = [{"name": row[1], "category": row[2], "image_name": row[3]} for row in cursor.fetchall()]
    return GetItemResponse(items=items)

    # <<jsonの場合>>
    # with open('items.json', 'r') as f:
    #     item_all = json.load(f)
    #     items = item_all.get('items',[])#？？？
    # return GetItemResponse(items = items)

class GetItemByID(BaseModel):
    name: str
    category: str
    image: str

@app.get('/items/{item_id}', response_model = GetItemByID)
def get_item_by_id(item_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT name, category, image_name FROM items WHERE id = ?", (item_id,)) # SQLインジェクションを防ぐ
    item = cursor.fetchone()
    if not item:
        raise HTTPException(status_code=404, detail=f"Item with id: {item_id} not found")
    return GetItemByID(name=item[0], category=item[1], image=item[2])

    # <<jsonの場合>>
    # with open('items.json', 'r') as f:
    #     item_all = json.load(f)
    #     items = item_all.get('items',[])
    # try: 
    #     items[int(item_id)-1]
    # except(IndexError):
    #     raise IndexError(f"Invalid item_id: {item_id}. ID must be between 1 and {len(items)}")

class AddItemResponse(BaseModel):
    message: str

# add_item is a handler to add a new item for POST /items .
@app.post("/items", response_model=AddItemResponse)
def add_item(
    name: str = Form(...),
    category: str = Form(...), #フォームデータとして受け取る
    image: UploadFile = File(...), #ファイルとして受け取る
    db: sqlite3.Connection = Depends(get_db),
):
    if not name or not category or not image:
        raise HTTPException(status_code=400, detail="All fields are required")
    
    hashed_image = save_image(image)

    insert_item(Item(name=name,category=category, image_name=hashed_image), db)
    return AddItemResponse(**{"message": f"item received: {name}, category: {category}, hashed_image: {hashed_image}"})


# get_image is a handler to return an image for GET /images/{filename} .
@app.get("/image/{image_name}")
async def get_image(image_name):
    # Create image path
    image = images / image_name

    if not image_name.endswith(".jpg"):
        raise HTTPException(status_code=400, detail="Image path does not end with .jpg")

    if not image.exists():
        logger.debug(f"Image not found: {image}")
        image = images / "default.jpg"

    return FileResponse(image)


class Item(BaseModel):
    name: str
    category: str
    image_name: str


def insert_item(item: Item, db: sqlite3.Connection):
# <<jsonの場合>>
    # STEP 4-1: add an implementation to store an item
    # with open('items.json') as f:
    #     d_update = json.load(f)
    # item_detail = {
    #             "name": item.name,
    #             "category": item.category,
    #             "image": item.image_name
    #         }
    # d_update['items'].append(item_detail)

    # with open('items.json', 'w') as f:
    #     json.dump(d_update, f, indent=2)

    cursor = db.cursor()
    # categories テーブルにカテゴリが存在するか確認
    cursor.execute("SELECT id FROM categories WHERE name = ?", (item.category,))
    category_row = cursor.fetchone()

    if category_row:
        category_id = category_row["id"]
    else:
        # カテゴリが存在しない場合、新しく追加
        cursor.execute("INSERT INTO categories (name) VALUES (?)", (item.category,))
        category_id = cursor.lastrowid  # 追加したカテゴリの ID を取得
    

    cursor.execute(
        "INSERT INTO items (name, category_id, image_name) VALUES (?, ?, ?)",
        (item.name, category_id, item.image_name)
    )
    db.commit()


class SearchResponse(BaseModel):
    items:List[Item] #複数のitemsを返すからリストじゃないといけない

@app.get('/search', response_model = SearchResponse)
def search_items(
        keyword: str = Query(...,min_length=1, description='Search keyword'),
        db: sqlite3.Connection = Depends(get_db),
):
    cursor = db.cursor()
    cursor.execute("SELECT name, category, image_name FROM items WHERE name LIKE ?", (f"%{keyword}%",)) 
    rows = cursor.fetchall()
    cursor.close()
    items = [Item(name=row["name"], category=row["category"], image_name=row["image_name"]) for row in rows]
    return SearchResponse(items=items)
