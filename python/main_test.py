from fastapi.testclient import TestClient
from main import app, get_db
import pytest
import sqlite3
import os
import pathlib

# STEP 6-4: uncomment this test setup
test_db = pathlib.Path(__file__).parent.resolve() / "db" / "test_mercari.sqlite3"

def override_get_db():
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def db_connection():
    # Before the test is done, create a test database
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    # ✅ categories テーブルを作成
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )"""
    )
    
    # ✅ items テーブルを作成（category_id を使用）
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            image_name TEXT NOT NULL,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )"""
    )
    conn.commit()
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries

    yield conn

    conn.close()
    # After the test is done, remove the test database
    if test_db.exists():
        test_db.unlink() # Remove the file

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.mark.parametrize(
    "want_status_code, want_body",
    [
        (200, {"message": "Hello, world!"}),
    ],
)
def test_hello(want_status_code, want_body):
    response = client.get("/")
    response_body = response.json()
    # STEP 6-2: confirm the status code
    assert response.status_code == want_status_code, f'Expected {want_status_code}, got {response.status_code}'
    # STEP 6-2: confirm response body
    assert response_body == want_body, f'Expected {want_body}, got {response_body}'


# STEP 6-4: uncomment this test
@pytest.mark.parametrize(
    "args, want_status_code",
    [
        ({"name":"used iPhone 16e", "category":"phone"}, 200),
        ({"name":"", "category":"phone"}, 400),
    ],
)
def test_add_item_e2e(args,want_status_code,db_connection):
    cursor = db_connection.cursor()

    # ✅ 1. カテゴリーを追加して `category_id` を取得
    cursor.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (args["category"],))
    cursor.execute("SELECT id FROM categories WHERE name = ?", (args["category"],))
    category_row = cursor.fetchone()
    assert category_row is not None, "Category not found in database"
    category_id = category_row["id"]

    # ✅ 2. `args` の `category` を `category_id` に変換
    new_args = args.copy()
    new_args["category_id"] = category_id
    del new_args["category"]  # `category` は main.py に渡す必要がないため削除

    # ✅ 3. アイテムを登録
    with open("test_image.jpg", "rb") as image_file:
        files = {"image": ("test_image.jpg", image_file, "image/jpeg")}
        response = client.post("/items/", data=new_args, files=files)

    assert response.status_code == want_status_code

    if want_status_code >= 400:
        return

    # ✅ 4. DBに正しく登録されたか確認
    cursor.execute("SELECT * FROM items WHERE name = ? AND category_id = ?", (args["name"], category_id))
    db_item = cursor.fetchone()
    assert db_item is not None
    assert dict(db_item)["name"] == args["name"]
        
    # # Check if the response body is correct
    # response_data = response.json()
    # assert "message" in response_data

    # # Check if the data was saved to the database correctly
    # cursor = db_connection.cursor()
    # cursor.execute("SELECT * FROM items WHERE name = ?", (args["name"],))
    # db_item = cursor.fetchone()
    # assert db_item is not None
    # assert dict(db_item)["name"] == args["name"]
