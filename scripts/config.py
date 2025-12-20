# config.py
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "databases/SQLite.db")

WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", 8000))

DEFAULT_CHAT_IDS = [
    "n.lyzunenko@test-123645965336.bizml.ru",
    "AoLJrsA6x1EdRf3xNm4",
]
if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in .env (exmaple .env.example)")
