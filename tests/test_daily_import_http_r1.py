import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing
from http.server import ThreadingHTTPServer
from pathlib import Path

from backend.api.routes import ApiHandler
from backend.db import database


SAMPLE = """10/9 李力 7495
1️⃣09:30 大阪送机关西 WhatsApp*代收13000日元
2️⃣10:40 关西举牌接机大阪 指定时间 微信
3️⃣13:00 大阪送机关西 微信
4️⃣14:00 关西举牌接机大阪 line
5️⃣17:00 大阪送机关西 微信
6️⃣18:00 关西举牌接机大阪 指定时间 微信"""


class DailyImportHttpR1Test(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_db = database.DB_PATH
        database.DB_PATH = Path(self.temp.name) / "daily-import-http.sqlite3"
        database.init_db(seed=True)
        with closing(database.get_connection()) as conn:
            conn.execute(
                "INSERT INTO drivers (tenant_id, name, status, driver_status) VALUES (1, '李力', 'available', 'available')"
            )
            self.driver_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.execute(
                "INSERT INTO vehicles (tenant_id, plate_number, plate_no, status) VALUES (1, '大阪7495', '大阪7495', 'available')"
            )
            self.vehicle_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.commit()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ApiHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        login = self.request("POST", "/api/auth/login", {"username": "admin", "password": "admin123"})
        self.token = login["token"]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        database.DB_PATH = self.original_db
        self.temp.cleanup()

    def request(self, method, path, payload=None):
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if getattr(self, "token", None):
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            self.fail(f"HTTP {exc.code} {path}: {body}")

    @staticmethod
    def import_orders(parsed_group):
        return [
            {
                **item["parsed"],
                "order_date": item["date"],
                "end_date": item["parsed"].get("end_date") or item["date"],
                "start_time": item["time"],
                "pickup_location": item["parsed"].get("pickup_location") or "待补",
                "dropoff_location": item["parsed"].get("dropoff_location") or "待补",
            }
            for item in parsed_group["orders"]
        ]

    def test_parse_assign_status_retry_and_run_group_chain(self):
        parsed = self.request(
            "POST",
            "/api/dispatch-mobile/parser/daily",
            {"text": SAMPLE, "default_year": 2026, "default_date": "2026-10-10"},
        )
        group = parsed["groups"][0]
        self.assertEqual((group["serviceDate"], len(group["orders"])), ("2026-10-09", 6))
        payload = {
            "client_batch_id": "http-r1-20261009-li-7495",
            "groups": [{
                "client_group_index": 0,
                "service_date": group["serviceDate"],
                "driver_id": self.driver_id,
                "vehicle_id": self.vehicle_id,
                "driver_name": "李力",
                "vehicle_code": "7495",
                "orders": self.import_orders(group),
            }],
        }
        first = self.request("POST", "/api/dispatch-mobile/daily-import/assign", payload)
        retry = self.request("POST", "/api/dispatch-mobile/daily-import/assign", payload)
        status = self.request(
            "GET",
            "/api/dispatch-mobile/daily-import/status?" + urllib.parse.urlencode({"client_batch_id": payload["client_batch_id"]}),
        )
        run_groups = self.request("GET", "/api/dispatch-mobile/run-groups?date=2026-10-09")
        self.assertEqual(first["imported_order_count"], 6)
        self.assertTrue(retry["idempotent_replay"])
        self.assertEqual(retry["order_ids"], first["order_ids"])
        self.assertEqual(status["batch"]["status"], "succeeded")
        self.assertEqual(run_groups["groups"][0]["order_count"], 6)
        self.assertEqual(run_groups["groups"][0]["document_status"], "none")
        with closing(database.get_connection()) as conn:
            assignment_states = conn.execute(
                "SELECT DISTINCT execution_status, published_at FROM assignments ORDER BY execution_status"
            ).fetchall()
            notification_count = conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0]
        self.assertEqual([(row["execution_status"], row["published_at"]) for row in assignment_states], [("draft", None)])
        self.assertEqual(notification_count, 0)


if __name__ == "__main__":
    unittest.main()
