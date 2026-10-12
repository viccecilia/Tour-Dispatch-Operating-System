import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image

from backend.db import database
from backend.services.resource_service import (
    create_driver,
    create_vehicle,
    create_vehicle_inspection_record,
    get_driver,
    get_vehicle,
    update_driver,
)
from backend.services.tenant_context import set_current_tenant_id
from backend.services.resource_library_service import _as_searchable_pdf, upload_vehicle_resource_document


class MobileResourceReminderUpdatesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_db_path = database.DB_PATH
        self.old_library_root = os.environ.get("DISPATCH_RESOURCE_LIBRARY_ROOT")
        database.DB_PATH = Path(self.temp.name) / "reminders.sqlite3"
        os.environ["DISPATCH_RESOURCE_LIBRARY_ROOT"] = self.temp.name
        database.init_db(seed=False)
        with database.get_connection() as conn:
            conn.execute("INSERT INTO tenants (id, name, slug) VALUES (8204, 'Daitora', 'DTR')")
            conn.commit()
        set_current_tenant_id(8204)

    def tearDown(self):
        set_current_tenant_id(None)
        database.DB_PATH = self.old_db_path
        if self.old_library_root is None:
            os.environ.pop("DISPATCH_RESOURCE_LIBRARY_ROOT", None)
        else:
            os.environ["DISPATCH_RESOURCE_LIBRARY_ROOT"] = self.old_library_root
        self.temp.cleanup()

    def test_driver_dates_and_vehicle_records_are_tenant_scoped(self):
        driver = create_driver({"name": "提醒测试司机", "status": "available"}, 8204)
        vehicle = create_vehicle({"plate_number": "なにわ300あ9999", "status": "available"}, 8204)

        updated_driver = update_driver(str(driver["id"]), {
            "health_check_due_date": "2026-10-12",
            "license_due_date": "2027-10-12",
            "residence_due_date": "2028-10-12",
        }, 8204)
        self.assertEqual(updated_driver["health_check_due_date"], "2026-10-12")
        self.assertEqual(updated_driver["license_due_date"], "2027-10-12")
        self.assertEqual(updated_driver["residence_due_date"], "2028-10-12")
        self.assertIsNone(update_driver(str(driver["id"]), {"license_due_date": "2029-10-12"}, 1))

        statutory = create_vehicle_inspection_record(str(vehicle["id"]), {
            "inspection_type": "shaken",
            "inspection_date": "2026-10-12",
            "source": "dispatch_mobile",
        }, 8204)
        self.assertEqual(statutory["inspection_type"], "shaken")
        self.assertEqual(get_vehicle(str(vehicle["id"]), 8204)["shaken_due_date"], "2027-10-12")
        record = create_vehicle_inspection_record(str(vehicle["id"]), {
            "inspection_type": "inspection",
            "inspection_date": "2026-10-12",
            "source": "dispatch_mobile",
        }, 8204)
        self.assertEqual(record["inspection_type"], "inspection")
        self.assertEqual(record["inspection_date"], "2026-10-12")
        self.assertEqual(get_driver(str(driver["id"]), 8204)["name"], "提醒测试司机")
        self.assertEqual(get_vehicle(str(vehicle["id"]), 8204)["plate_number"], "なにわ300あ9999")

    def test_photo_document_is_normalized_to_a_pdf(self):
        image = Image.new("RGB", (80, 50), "white")
        source = BytesIO()
        image.save(source, format="JPEG")
        result = _as_searchable_pdf(source.getvalue(), "inspection.jpg", "image/jpeg")
        self.assertTrue(result.startswith(b"%PDF-"))

    def test_vehicle_upload_uses_plate_category_and_completion_date_as_name(self):
        image = Image.new("RGB", (80, 50), "white")
        source = BytesIO()
        image.save(source, format="JPEG")
        import base64
        saved = upload_vehicle_resource_document("なにわ300あ9999", "3个月点检", "2026-10-12", {
            "file_name": "camera.jpg",
            "content_type": "image/jpeg",
            "file_base64": base64.b64encode(source.getvalue()).decode("ascii"),
        })
        document = saved["document"]
        self.assertEqual(document["file_name"], "なにわ300あ9999_3个月点检_2026-10-12.pdf")
        self.assertTrue((Path(self.temp.name) / document["file_key"]).read_bytes().startswith(b"%PDF-"))


if __name__ == "__main__":
    unittest.main()
