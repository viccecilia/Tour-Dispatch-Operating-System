import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
RUNTIME_DIR = BASE_DIR / "runtime"


def _load_env_file() -> None:
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


_load_env_file()

HOST = os.environ.get("WX_DISPATCH_HOST", "127.0.0.1")
PORT = int(os.environ.get("WX_DISPATCH_PORT", os.environ.get("PORT", "18765")))
BASE_URL = os.environ.get("WX_DISPATCH_BASE_URL", f"http://{HOST}:{PORT}")
DB_PATH = Path(os.environ.get("WX_DISPATCH_DB", str(RUNTIME_DIR / "wx_dispatch.sqlite3"))).resolve()
DEMO_MODE = _bool_env("WX_DISPATCH_DEMO_MODE", True)
RESET_DEMO_ON_START = _bool_env("WX_DISPATCH_RESET_DEMO_ON_START", False)
LOG_LEVEL = os.environ.get("WX_DISPATCH_LOG_LEVEL", "INFO").upper()
LOG_DIR = Path(os.environ.get("WX_DISPATCH_LOG_DIR", str(RUNTIME_DIR / "logs"))).resolve()
BACKUP_DIR = Path(os.environ.get("WX_DISPATCH_BACKUP_DIR", str(RUNTIME_DIR / "backups"))).resolve()

DEFAULT_ADMIN = {
    "username": os.environ.get("WX_DISPATCH_ADMIN_USERNAME", "admin"),
    "password": os.environ.get("WX_DISPATCH_ADMIN_PASSWORD", "admin123"),
    "role": "admin",
    "display_name": os.environ.get("WX_DISPATCH_ADMIN_DISPLAY_NAME", "系统管理员"),
}


def ensure_runtime_dirs() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
