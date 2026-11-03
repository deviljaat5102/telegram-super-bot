import sqlite3
from datetime import datetime, timezone

from config import DATABASE_PATH


def _connect():
    return sqlite3.connect(DATABASE_PATH)


def init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_at TEXT NOT NULL
            )
        """)


def add_subscriber(user):
    with _connect() as conn:
        conn.execute(
            """INSERT INTO subscribers (user_id, username, first_name, joined_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   username = excluded.username,
                   first_name = excluded.first_name""",
            (
                user.id,
                user.username,
                user.first_name,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def remove_subscriber(user_id):
    with _connect() as conn:
        conn.execute("DELETE FROM subscribers WHERE user_id = ?", (user_id,))


def get_subscribers():
    with _connect() as conn:
        rows = conn.execute("SELECT user_id FROM subscribers").fetchall()
    return [row[0] for row in rows]


def subscriber_count():
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM subscribers").fetchone()[0]
