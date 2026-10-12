from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from contextlib import closing
from copy import deepcopy
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from backend.db import database
from backend.services import dispatch_service, parser_service
from backend.services import run_document_service as document_service
from backend.services.document_model_service import build_document_snapshot
from backend.services.tenant_context import set_current_tenant_id
from backend.services.v014_hire_document_renderer import render_hire_sample_packet
from generate_v014_hire_sample_pdf import sample_group


OUTPUT = ROOT / "output" / "pdf"
JP_FONT = ROOT / "backend" / "assets" / "fonts" / "NotoSansJP-VF.ttf"
RAW_SIX = """10/9 李力 7495
1️⃣09:30 大阪送机关西 WhatsApp*代收13000日元
2️⃣10:40 关西举牌接机大阪 指定时间 微信
3️⃣13:00 大阪送机关西 微信
4️⃣14:00 关西举牌接机大阪 line
5️⃣17:00 大阪送机关西 微信
6️⃣18:00 关西举牌接机大阪 指定时间 微信"""
ACTOR = {
    "id": 11,
    "tenant_id": 1,
    "username": "phase2c2r2-evidence",
    "display_name": "R2 本地核验",
    "role": "operations_manager",
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def airport_sample(target: Path) -> dict[str, object]:
    temporary = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    temp_root = Path(temporary.name)
    original_db = database.DB_PATH
    original_runtime = document_service.RUNTIME_DIR
    try:
        database.DB_PATH = temp_root / "evidence.sqlite3"
        document_service.RUNTIME_DIR = temp_root / "runtime"
        database.init_db(seed=False)
        set_current_tenant_id(1)
        with closing(database.get_connection()) as connection:
            connection.execute("INSERT INTO tenants (id, name, slug) VALUES (1, '大寅 R2 本地证据', 'daitora-r2-local')")
            connection.execute("INSERT INTO drivers (id, tenant_id, name, driver_code, office, status, driver_status) VALUES (9, 1, '李力', 'LL', '大阪営業所', 'available', 'available')")
            connection.execute("INSERT INTO vehicles (id, tenant_id, plate_no, plate_number, vehicle_type, seats, seat_count, status) VALUES (9, 1, '大阪7495', '大阪 300 あ 7495', 'Alphard', 7, 7, 'available')")
            connection.execute(
                """
                INSERT INTO company_registrations (
                    managing_tenant_id, company_type, tenant_id, company_code,
                    company_name, registered_name, address, contact_name,
                    contact_phone, contact_email, status
                ) VALUES (
                    1, 'carrier', 1, 'DAITORA', '株式会社大寅', '株式会社大寅',
                    '〒551-0013 大阪府大阪市大正区小林西2丁目10-3',
                    '運行管理', '06-6710-9861', 'dispatch@example.invalid', 'approved'
                )
                """
            )
            connection.commit()
        parsed = parser_service.parse_daily_assignment_text(RAW_SIX, base_year=2026)["groups"][0]
        imported = dispatch_service.import_daily_assignment_group(
            {
                "driver_id": 9,
                "vehicle_id": 9,
                "orders": [item["parsed"] for item in parsed["orders"]],
            },
            ACTOR,
        )
        group_key = document_service.group_key("2026-10-09", 9, 9)
        document = document_service.generate_run_document(group_key, ACTOR)
        generated = (
            document_service.RUNTIME_DIR
            / "uploads"
            / "run_documents"
            / "1"
            / "2026-10-09"
            / document["file_name"]
        )
        shutil.copyfile(generated, target)
        with closing(database.get_connection()) as connection:
            orders = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM orders WHERE id IN ({}) ORDER BY start_time".format(
                        ",".join("?" for _ in imported["order_ids"])
                    ),
                    imported["order_ids"],
                )
            ]
        city_locations = [
            orders[0]["pickup_location"],
            orders[1]["dropoff_location"],
            orders[2]["pickup_location"],
            orders[3]["dropoff_location"],
            orders[4]["pickup_location"],
            orders[5]["dropoff_location"],
        ]
        return {
            "file": str(target),
            "sha256": file_sha256(target),
            "pages": len(PdfReader(str(target)).pages),
            "renderer_version": document_service.DOCUMENT_RENDERER_VERSION,
            "times": [[row["start_time"], row["end_time"]] for row in orders],
            "hotels": city_locations,
            "document_id": document["document_id"],
            "document_version_id": document["document_version_id"],
        }
    finally:
        database.DB_PATH = original_db
        document_service.RUNTIME_DIR = original_runtime
        set_current_tenant_id(None)
        temporary.cleanup()


def charter_sample(target: Path) -> dict[str, object]:
    group = sample_group()
    charter_group = {
        **deepcopy(group),
        "business_date": "2026-10-10",
        "driver_name": "董星",
        "driver_office": "京都営業所",
        "plate_number": "京都300あ3827",
        "operations_manager": "朱 英心",
        "garage_out_time": "08:00",
        "garage_in_time": "18:00",
        "orders": [deepcopy(group["orders"][4])],
    }
    snapshot = build_document_snapshot(charter_group, "docv-v014-charter-fontfix-evidence")
    snapshot["created_date"] = "2026-10-09"
    snapshot["route_code"] = "R9"
    pages = render_hire_sample_packet(snapshot, target, jp_font_path=JP_FONT)
    return {
        "file": str(target),
        "sha256": file_sha256(target),
        "pages": pages,
        "renderer_version": document_service.DOCUMENT_RENDERER_VERSION,
    }


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = {
        "airport": airport_sample(OUTPUT / "DAITORA_phase2c2_r2_fontfix_raw_six_airport.pdf"),
        "charter": charter_sample(OUTPUT / "DAITORA_phase2c2_r2_fontfix_charter.pdf"),
    }
    report = OUTPUT / "DAITORA_phase2c2_r2_fontfix_samples.json"
    report.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
