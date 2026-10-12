import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.db import database


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "import_fixed_tour_route_catalog.py"
SPEC = importlib.util.spec_from_file_location("import_fixed_tour_route_catalog", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load route catalog importer: {SCRIPT_PATH}")
IMPORTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IMPORTER)
import_catalog = IMPORTER.import_catalog
load_catalog = IMPORTER.load_catalog
resolve_tenant = IMPORTER.resolve_tenant


class FixedTourRouteCatalogTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_db_path = database.DB_PATH
        database.DB_PATH = Path(self.temp.name) / "catalog.sqlite3"
        database.init_db(seed=False)
        self.conn = sqlite3.connect(database.DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("INSERT INTO tenants (id, name, slug) VALUES (8204, 'Daitora', 'DTR')")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        database.DB_PATH = self.old_db_path
        self.temp.cleanup()

    def test_catalog_import_is_active_complete_and_idempotent(self):
        routes = load_catalog()
        first = import_catalog(self.conn, 8204, routes, apply=True)
        self.conn.commit()
        second = import_catalog(self.conn, 8204, routes, apply=True)
        self.conn.commit()

        self.assertEqual((len(routes), first["inserted_count"], second["skipped_count"]), (10, 10, 10))
        counts = self.conn.execute(
            """
            SELECT
                COUNT(*) AS routes,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active,
                (SELECT COUNT(*) FROM fixed_tour_route_prices WHERE tenant_id = 8204) AS prices
            FROM fixed_tour_routes
            WHERE tenant_id = 8204
            """
        ).fetchone()
        self.assertEqual((counts["routes"], counts["active"], counts["prices"]), (10, 10, 0))
        identity = self.conn.execute(
            "SELECT applicant_name, application_method FROM fixed_tour_routes WHERE tenant_id = 8204 LIMIT 1"
        ).fetchone()
        self.assertEqual((identity["applicant_name"], identity["application_method"]), ("SPI", "ウェブサイト"))

    def test_unknown_times_are_not_fabricated_and_two_day_route_is_preserved(self):
        import_catalog(self.conn, 8204, load_catalog(), apply=True)
        self.conn.commit()
        osaka_nara = self.conn.execute(
            "SELECT default_start_time, default_end_time, standard_duration_minutes FROM fixed_tour_routes WHERE route_code = 'DT-OSAKA-NARA-RT'"
        ).fetchone()
        kumano = self.conn.execute(
            "SELECT id, default_end_time, standard_duration_minutes, route_summary FROM fixed_tour_routes WHERE route_code = 'DT-KUMANO-SANZAN-2D'"
        ).fetchone()
        kumano_stops = self.conn.execute(
            "SELECT location_name, default_departure_time, note FROM fixed_tour_route_stops WHERE route_id = ? ORDER BY sequence_no",
            (kumano["id"],),
        ).fetchall()

        self.assertEqual((osaka_nara["default_start_time"], osaka_nara["default_end_time"], osaka_nara["standard_duration_minutes"]), ("09:00", None, None))
        self.assertIsNone(kumano["default_end_time"])
        self.assertIsNone(kumano["standard_duration_minutes"])
        self.assertIn("第2日", kumano["route_summary"])
        self.assertEqual(kumano_stops[4]["default_departure_time"], "08:30")
        self.assertIn("第2日", kumano_stops[4]["note"])

    def test_existing_route_is_preserved_and_daitora_tenant_is_resolved(self):
        routes = load_catalog()
        import_catalog(self.conn, 8204, routes, apply=True)
        self.conn.execute(
            "UPDATE fixed_tour_routes SET route_name = '人工修改后名称' WHERE tenant_id = 8204 AND route_code = ?",
            (routes[0]["route_code"],),
        )
        self.conn.commit()
        result = import_catalog(self.conn, 8204, routes, apply=True)
        self.conn.commit()
        name = self.conn.execute(
            "SELECT route_name FROM fixed_tour_routes WHERE tenant_id = 8204 AND route_code = ?",
            (routes[0]["route_code"],),
        ).fetchone()[0]

        self.assertEqual(resolve_tenant(self.conn)["id"], 8204)
        self.assertEqual(result["skipped_count"], 10)
        self.assertEqual(name, "人工修改后名称")


if __name__ == "__main__":
    unittest.main()
