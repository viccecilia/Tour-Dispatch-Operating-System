from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
RUNTIME_DIR = BASE_DIR / "runtime"
DB_PATH = RUNTIME_DIR / "wx_dispatch.sqlite3"

DEFAULT_ADMIN = {
    "username": "admin",
    "password": "admin123",
    "role": "admin",
    "display_name": "系统管理员",
}
