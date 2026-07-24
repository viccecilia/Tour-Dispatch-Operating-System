from __future__ import annotations

import os
import sys
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
for path in (ROOT, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from generate_account_activity_window import collect_sources, render_html  # noqa: E402


HOST = os.environ.get("ACTIVITY_WINDOW_HOST", "127.0.0.1")
PORT = int(os.environ.get("ACTIVITY_WINDOW_PORT", "18770"))
OUTPUT = Path(
    os.environ.get(
        "ACTIVITY_WINDOW_OUTPUT",
        "/var/www/tourflow-admin/activity-window/index.html",
    )
)
REFRESH_FORM = """
<form method="post" action="/activity-window/refresh"
      style="position:absolute;right:28px;top:22px">
  <button type="submit"
          style="border:1px solid rgba(255,255,255,.4);border-radius:9px;
                 padding:10px 16px;background:#246bfe;color:#fff;
                 font-weight:900;cursor:pointer">
    刷新线上数据
  </button>
</form>
"""


def refresh_page() -> str:
    data = collect_sources("local", fetch_server=False)
    rendered = render_html(data).replace("</header>", f"{REFRESH_FORM}</header>", 1)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=OUTPUT.parent,
        delete=False,
        prefix=".activity-window-",
        suffix=".html",
    ) as handle:
        handle.write(rendered)
        temporary = Path(handle.name)
    temporary.replace(OUTPUT)
    return str(data.get("generated_at") or "")


class Handler(BaseHTTPRequestHandler):
    server_version = "TourFlowActivityWindow/1.0"

    def log_message(self, format: str, *args) -> None:
        print(f"{self.address_string()} - {format % args}", flush=True)

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            self._send_text("ok")
            return
        if self.path not in {"/", ""}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not OUTPUT.exists():
            refresh_page()
        body = OUTPUT.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/refresh":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            refresh_page()
        except Exception as exc:
            self._send_text(f"refresh failed: {exc}", HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", "/activity-window/")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _send_text(self, text: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
