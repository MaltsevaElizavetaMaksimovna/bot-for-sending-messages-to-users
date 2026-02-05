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

def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


AUTH_ENABLED = _env_bool("AUTH_ENABLED", False)
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
VK_CLIENT_ID = os.getenv("VK_CLIENT_ID")
VK_CLIENT_SECRET = os.getenv("VK_CLIENT_SECRET")
VK_REDIRECT_URI = os.getenv("VK_REDIRECT_URI", "http://localhost:8000/auth/vk/callback")
ALLOWED_VK_IDS = {
    value.strip()
    for value in os.getenv("ALLOWED_VK_IDS", "").split(",")
    if value.strip()
}

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in .env (example: .env.example)")
