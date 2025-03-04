import os
import logging
import pathlib
from fastapi import FastAPI, Form, HTTPException, Depends, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from pydantic import BaseModel
from contextlib import asynccontextmanager
import json
import hashlib


# Define the path to the images & sqlite3 database
images = pathlib.Path(__file__).parent.resolve() / "images"
db = pathlib.Path(__file__).parent.resolve() / "db" / "mercari.sqlite3"


def get_db():
    if not db.exists():
        yield

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    try:
        yield conn
    finally:
        conn.close()


# STEP 5-1: set up the database connection
def setup_database():
    pass


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
    file_path = os.path.join("images", file_name)

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
def get_items():#SQLiteの接続も？
    with open('items.json', 'r') as f:
        item_all = json.load(f)
        items = item_all.get('items',[])#？？？
    # return GetItemResponse(**{"items": [{item['name'] : item['category'] for item in item_dic}]})
    return GetItemResponse(items = items)

class GetIDItem(BaseModel):
    name: str
    category: str
    image: str

@app.get('/items/{item_id}', response_model = GetIDItem)
def get_iditem(item_id: int):
    with open('items.json', 'r') as f:
        item_all = json.load(f)
        items = item_all.get('items',[])
    return items[int(item_id)-1]

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
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    if not category:
        raise HTTPException(status_code=400, detail="category is required")
    if not image:
        raise HTTPException(status_code=400, detail="image is required")
    
    image_name = save_image(image)

    insert_item(Item(name=name,category=category, image_name=image_name))
    return AddItemResponse(**{"message": f"item received: {name}, category: {category}, image_name: {image_name}"})


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


def insert_item(item: Item):
    # STEP 4-1: add an implementation to store an item
    with open('items.json') as f:
        d_update = json.load(f)

    item_detail = {
                "name": item.name,
                "category": item.category,
                "image": item.image_name
            }

    d_update['items'].append(item_detail)

    with open('items.json', 'w') as f:
        json.dump(d_update, f, indent=2)
    pass
