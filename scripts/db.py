import sqlite3
import threading
from .config import DB_PATH

_db_lock = threading.Lock()
_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_conn.row_factory = sqlite3.Row
from datetime import datetime, timezone


def init_db():
    """Создаём таблицы, если ещё нет"""
    with _db_lock:
        cur = _conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS message_query (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT,
                img_url TEXT,
                img_file_name TEXT,
                url_for_button TEXT,
                text_for_button TEXT,
                message_time TEXT,
                users_group INTEGER
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS message_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                number_of_recipients INTEGER,
                url_follow_amount INTEGER
            )
        """)
        _conn.commit()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS message_delivery (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                chat_id TEXT NOT NULL,
                delivered_at TEXT NOT NULL,
                UNIQUE(message_id, chat_id)
            )
        """)


def fetch_pending_messages():
    """Берём сообщения, которых ещё нет в feedback (то есть не разосланы)."""
    with _db_lock:
        cur = _conn.cursor()
        cur.execute("""
            SELECT mq.*
            FROM message_query mq
            LEFT JOIN message_feedback mf
              ON mq.id = mf.message_id
            WHERE mf.message_id IS NULL
        """)
        return cur.fetchall()


def insert_feedback(message_id: int, number_of_recipients: int, url_follow_amount: int = 0):
    with _db_lock:
        cur = _conn.cursor()
        cur.execute("""
            INSERT INTO message_feedback (message_id, number_of_recipients, url_follow_amount)
            VALUES (?, ?, ?)
        """, (message_id, number_of_recipients, url_follow_amount))
        _conn.commit()


def insert_message_query(message: str, message_time: str, users_group: int = 1):
    """Вызывается из веба — создать новую рассылку."""
    with _db_lock:
        cur = _conn.cursor()
        cur.execute("""
            INSERT INTO message_query (message, message_time, users_group)
            VALUES (?, ?, ?)
        """, (message, message_time, users_group))
        _conn.commit()

def get_delivered_chat_ids(message_id: int) -> set[str]:
    """Каким chat_id уже успешно доставили message_id."""
    with _db_lock:
        cur = _conn.cursor()
        cur.execute("""
            SELECT chat_id
            FROM message_delivery
            WHERE message_id = ?
        """, (message_id,))
        return {row["chat_id"] for row in cur.fetchall()}


def mark_delivered(message_id: int, chat_id: str):
    """Пометить доставку в конкретный chat_id (идемпотентно)."""
    delivered_at = datetime.now(timezone.utc).isoformat()
    with _db_lock:
        cur = _conn.cursor()
        # INSERT OR IGNORE — чтобы не падать при повторах
        cur.execute("""
            INSERT OR IGNORE INTO message_delivery (message_id, chat_id, delivered_at)
            VALUES (?, ?, ?)
        """, (message_id, chat_id, delivered_at))
        _conn.commit()
def get_messages_with_stats():
    """Для странички /: список рассылок + сколько отправлено."""
    with _db_lock:
        cur = _conn.cursor()
        cur.execute("""
            SELECT mq.id, mq.message, mq.message_time,
                   IFNULL(mf.number_of_recipients, 0) AS sent
            FROM message_query mq
            LEFT JOIN message_feedback mf
              ON mq.id = mf.message_id
            ORDER BY mq.id DESC
        """)
        return cur.fetchall()


def get_message_stats(message_id: int):
    """Для API /api/stats/<id>."""
    with _db_lock:
        cur = _conn.cursor()
        cur.execute("""
            SELECT mq.id, mq.message, mq.message_time,
                   IFNULL(mf.number_of_recipients, 0) AS sent,
                   IFNULL(mf.url_follow_amount, 0) AS clicks
            FROM message_query mq
            LEFT JOIN message_feedback mf
              ON mq.id = mf.message_id
            WHERE mq.id = ?
        """, (message_id,))
        return cur.fetchone()