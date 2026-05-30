from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.config import BACKUP_DIR, BASE_DIR, DB_PATH, LOG_DIR, PORT, TRIAL_MODE


SERVICE_NAME = "tourflow-trial-api.service"


def get_system_status() -> dict[str, Any]:
    frontend_index = BASE_DIR / "frontend" / "dist" / "index.html"
    web_index = Path("/var/www/tourflow-admin/index.html")
    return {
        "ok": True,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "environment": "trial" if TRIAL_MODE else os.environ.get("WX_DISPATCH_ENV", "local") or "local",
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "pid": os.getpid(),
        "port": PORT,
        "database": str(DB_PATH),
        "database_exists": DB_PATH.exists(),
        "database_size_mb": round(DB_PATH.stat().st_size / 1024 / 1024, 2) if DB_PATH.exists() else 0,
        "frontend_asset": _frontend_asset(web_index if web_index.exists() else frontend_index),
        "service": _systemctl_status(),
    }


def run_system_health() -> dict[str, Any]:
    checks = [
        {"name": "api_process", "ok": True, "detail": f"pid {os.getpid()}"},
        {"name": "database_file", "ok": DB_PATH.exists(), "detail": str(DB_PATH)},
        {"name": "log_dir", "ok": LOG_DIR.exists(), "detail": str(LOG_DIR)},
        {"name": "backup_dir", "ok": BACKUP_DIR.exists(), "detail": str(BACKUP_DIR)},
    ]
    return {"ok": all(item["ok"] for item in checks), "checks": checks, "timestamp": datetime.now().isoformat(timespec="seconds")}


def backup_database(actor: str = "system") -> dict[str, Any]:
    if not DB_PATH.exists():
        raise ValueError("database_not_found")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = BACKUP_DIR / f"manual_{stamp}_{actor.replace(':', '_')}.sqlite3"
    shutil.copy2(DB_PATH, target)
    return {
        "ok": True,
        "backup_path": str(target),
        "backup_name": target.name,
        "size_mb": round(target.stat().st_size / 1024 / 1024, 2),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def tail_backend_log(lines: int = 120) -> dict[str, Any]:
    log_file = LOG_DIR / "backend.log"
    if not log_file.exists():
        return {"ok": False, "log_file": str(log_file), "lines": []}
    rows = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    return {"ok": True, "log_file": str(log_file), "lines": rows[-max(1, min(lines, 500)) :]}


def schedule_api_restart() -> dict[str, Any]:
    if os.name == "nt":
        raise ValueError("restart_unavailable_on_windows")
    command = f"sleep 1; sudo -n systemctl restart {SERVICE_NAME}"
    subprocess.Popen(["bash", "-lc", command], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"ok": True, "scheduled": True, "service": SERVICE_NAME, "message": "restart_scheduled"}


def _systemctl_status() -> dict[str, Any]:
    if os.name == "nt":
        return {"available": False, "active": None}
    try:
        proc = subprocess.run(["systemctl", "is-active", SERVICE_NAME], capture_output=True, text=True, timeout=3)
        return {"available": True, "active": proc.stdout.strip() or proc.stderr.strip(), "returncode": proc.returncode}
    except Exception as exc:
        return {"available": False, "active": None, "error": str(exc)}


def _frontend_asset(index_path: Path) -> str:
    if not index_path.exists():
        return ""
    text = index_path.read_text(encoding="utf-8", errors="replace")
    marker = "/assets/"
    if marker not in text:
        return ""
    suffix = text.split(marker, 1)[1].split('"', 1)[0].split("'", 1)[0]
    return f"assets/{suffix}"
