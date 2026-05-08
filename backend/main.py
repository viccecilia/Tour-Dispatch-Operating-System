import logging
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.api.routes import ApiHandler
from backend.config import HOST, LOG_DIR, LOG_LEVEL, PORT, RESET_DEMO_ON_START, ensure_runtime_dirs
from backend.db.database import init_db


def configure_logging() -> None:
    ensure_runtime_dirs()
    log_file = LOG_DIR / "backend.log"
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


def create_server() -> ThreadingHTTPServer:
    if RESET_DEMO_ON_START:
        from scripts.reset_demo_db import main as reset_demo_db

        logging.info("RESET_DEMO_ON_START enabled; resetting demo database")
        reset_demo_db()
    else:
        init_db(seed=True)
    return ThreadingHTTPServer((HOST, PORT), ApiHandler)


def main() -> None:
    configure_logging()
    server = create_server()
    logging.info("WX Dispatch API running at http://%s:%s", HOST, PORT)
    logging.info("Dashboard: http://%s:%s/dashboard", HOST, PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        logging.info("WX Dispatch API stopped")
        server.server_close()


if __name__ == "__main__":
    main()
