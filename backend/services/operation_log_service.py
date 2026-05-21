import json
from datetime import datetime, timezone
from typing import Any

from backend.config import LOG_DIR, ensure_runtime_dirs


OPERATION_LOG = LOG_DIR / "operations.log"


def log_operation(action: str, path: str, payload: dict[str, Any] | None = None, actor: str | None = None) -> None:
    ensure_runtime_dirs()
    sanitized = _sanitize(payload or {})
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "actor": actor or "anonymous",
        "action": action,
        "path": path,
        "payload": sanitized,
    }
    with OPERATION_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _sanitize(payload: dict[str, Any]) -> dict[str, Any]:
    hidden = {"password", "token", "authorization"}
    result: dict[str, Any] = {}
    for key, value in payload.items():
        if key.lower() in hidden:
            result[key] = "***"
        elif isinstance(value, str) and len(value) > 240:
            result[key] = value[:240] + "...[truncated]"
        else:
            result[key] = value
    return result
