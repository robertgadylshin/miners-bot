import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "miners.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER UNIQUE NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    username TEXT DEFAULT '',
    full_name TEXT DEFAULT '',
    location_id INTEGER NOT NULL,
    role TEXT DEFAULT 'barista',
    tokens INTEGER DEFAULT 0,
    total_earned INTEGER DEFAULT 0,
    joined_at TEXT DEFAULT (datetime('now')),
    UNIQUE(telegram_id, location_id),
    FOREIGN KEY (location_id) REFERENCES locations(id)
);

CREATE TABLE IF NOT EXISTS task_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    task_key TEXT NOT NULL,
    task_name TEXT NOT NULL,
    photo_file_id TEXT NOT NULL,
    tokens_awarded INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    submitted_at TEXT DEFAULT (datetime('now')),
    reviewed_at TEXT,
    reviewed_by INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS admins (
    telegram_id INTEGER PRIMARY KEY,
    added_at TEXT DEFAULT (datetime('now'))
);
"""


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    db = get_db()
    db.executescript(SCHEMA)

    admin_id = os.environ.get("SUPER_ADMIN_ID")
    if admin_id:
        db.execute(
            "INSERT OR IGNORE INTO admins (telegram_id) VALUES (?)", (int(admin_id),)
        )

    db.commit()
    db.close()
    print("✅ Database initialized")
