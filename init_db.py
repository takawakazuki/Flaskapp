import sqlite3

# DBファイル名
DATABASE = "gasoline.db"

# DBに接続
db = sqlite3.connect(DATABASE)

# ユーザーテーブル
db.execute("""
CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    userid TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    name TEXT NOT NULL
)
""")

# locations テーブル
db.execute("""
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    price INTEGER NOT NULL
)
""")

# ride_records テーブル
db.execute("""
CREATE TABLE IF NOT EXISTS ride_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    go_location_id INTEGER,
    go_driver BOOLEAN,
    back_location_id INTEGER,
    back_driver BOOLEAN,
    FOREIGN KEY(user_id) REFERENCES user(id),
    FOREIGN KEY(go_location_id) REFERENCES locations(id),
    FOREIGN KEY(back_location_id) REFERENCES locations(id)
)
""")

# 初期データ投入（locations）
locations = [
    ("金沢大学", 50), ("津端", 50), ("宇野気", 100),
    ("西部", 100), ("県外（指定1）", 100),
    ("県外（指定2）", 200), ("その他", 0)
]

for name, price in locations:
    db.execute(
        "INSERT OR IGNORE INTO locations (name, price) VALUES (?, ?)",
        (name, price)
    )

# コミットしてクローズ
db.commit()
db.close()

print("初期化完了")
