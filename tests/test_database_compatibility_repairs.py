from __future__ import annotations

import sqlite3
import unittest

from backend.db import database


class DatabaseCompatibilityRepairTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE drivers (
                id INTEGER PRIMARY KEY,
                status TEXT,
                created_at TEXT,
                license_due_date TEXT,
                license_expires_at TEXT,
                health_check_due_date TEXT,
                medical_check_expires_at TEXT
            );
            CREATE TABLE vehicles (
                id INTEGER PRIMARY KEY,
                plate_no TEXT,
                seats INTEGER,
                created_at TEXT,
                next_inspection_due_date TEXT,
                inspection_expires_at TEXT,
                insurance_due_date TEXT,
                insurance_expires_at TEXT
            );
            """
        )

    def tearDown(self) -> None:
        self.connection.close()

    def test_existing_distinct_compatibility_dates_are_never_swapped(self) -> None:
        self.connection.execute(
            "INSERT INTO drivers(id, status, license_due_date, license_expires_at, health_check_due_date, medical_check_expires_at) VALUES (1, 'available', '2027-01-01', '2028-01-01', '2027-02-01', '2028-02-01')"
        )
        self.connection.execute(
            "INSERT INTO vehicles(id, plate_no, seats, next_inspection_due_date, inspection_expires_at, insurance_due_date, insurance_expires_at) VALUES (1, 'test', 5, '2027-03-01', '2028-03-01', '2027-04-01', '2028-04-01')"
        )
        before_driver = tuple(self.connection.execute("SELECT license_due_date, license_expires_at, health_check_due_date, medical_check_expires_at FROM drivers WHERE id=1").fetchone())
        before_vehicle = tuple(self.connection.execute("SELECT next_inspection_due_date, inspection_expires_at, insurance_due_date, insurance_expires_at FROM vehicles WHERE id=1").fetchone())

        database.ensure_driver_vehicle_schema(self.connection)
        database.ensure_driver_vehicle_schema(self.connection)

        after_driver = tuple(self.connection.execute("SELECT license_due_date, license_expires_at, health_check_due_date, medical_check_expires_at FROM drivers WHERE id=1").fetchone())
        after_vehicle = tuple(self.connection.execute("SELECT next_inspection_due_date, inspection_expires_at, insurance_due_date, insurance_expires_at FROM vehicles WHERE id=1").fetchone())
        self.assertEqual(after_driver, before_driver)
        self.assertEqual(after_vehicle, before_vehicle)

    def test_only_missing_compatibility_dates_are_filled(self) -> None:
        self.connection.execute(
            "INSERT INTO drivers(id, status, license_due_date, license_expires_at, health_check_due_date, medical_check_expires_at) VALUES (1, 'available', NULL, '2028-01-01', '2027-02-01', NULL)"
        )
        self.connection.execute(
            "INSERT INTO vehicles(id, plate_no, seats, next_inspection_due_date, inspection_expires_at, insurance_due_date, insurance_expires_at) VALUES (1, 'test', 5, NULL, '2028-03-01', '2027-04-01', NULL)"
        )

        database.ensure_driver_vehicle_schema(self.connection)
        database.ensure_driver_vehicle_schema(self.connection)

        self.assertEqual(
            tuple(self.connection.execute("SELECT license_due_date, license_expires_at, health_check_due_date, medical_check_expires_at FROM drivers WHERE id=1").fetchone()),
            ("2028-01-01", "2028-01-01", "2027-02-01", "2027-02-01"),
        )
        self.assertEqual(
            tuple(self.connection.execute("SELECT next_inspection_due_date, inspection_expires_at, insurance_due_date, insurance_expires_at FROM vehicles WHERE id=1").fetchone()),
            ("2028-03-01", "2028-03-01", "2027-04-01", "2027-04-01"),
        )


if __name__ == "__main__":
    unittest.main()
