import os
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.api.routes import ApiHandler
from backend.db.database import init_db


HOST = os.environ.get("WX_DISPATCH_HOST", "127.0.0.1")
PORT = int(os.environ.get("WX_DISPATCH_PORT", "8000"))


def create_server() -> ThreadingHTTPServer:
    init_db(seed=True)
    return ThreadingHTTPServer((HOST, PORT), ApiHandler)


def main() -> None:
    server = create_server()
    print(f"WX Dispatch API running at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
