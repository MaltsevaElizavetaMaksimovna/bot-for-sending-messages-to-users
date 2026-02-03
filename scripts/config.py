import os
from pathlib import Path
from dotenv import load_dotenv

# === Базовые пути ===
BASE_DIR = Path(__file__).resolve().parent        # scripts/
PROJECT_DIR = BASE_DIR.parent                    # корень проекта
DATABASES_DIR = PROJECT_DIR / "databases"        # databases/

# === .env ===
ENV_PATH = PROJECT_DIR / ".env"
load_dotenv(ENV_PATH)

# === Config ===
TOKEN = os.getenv("BOT_TOKEN")

DB_PATH = os.getenv(
    "DB_PATH",
    str(DATABASES_DIR / "SQLite.db")
)

WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", 8000))

DEFAULT_CHAT_IDS = [
    "last_dear@botdomain.bizml.ru",
    "AoLJrsA6x1EdRf3xNm4",
]

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in .env (example: .env.example)")

