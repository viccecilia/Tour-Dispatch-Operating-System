import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.db.database import init_db, get_connection
from backend.services.location_service import normalize_date_token, normalize_location_text, normalize_time_token
from backend.services.parser_service import parse_chinese_order, parse_text_to_draft


CHARTER_SAMPLES = [
    "5.09 11:00 大阪往返天桥立美山 包车 3代 绿 1900",
    "5.10 11:00 大阪-奈良-宇治-京都 包车 3代 绿 1500",
    "5.12 10:00 铃鹿-京都 包车 10座绿牌 儿童座椅*2 2000若綺 黃",
    "5.14 京都往返天桥立美山 包车 10座绿牌 儿童座椅*2（+座椅2000） 1900Kuan-Ying Chen",
]

TRANSFER_SAMPLES = [
    "3.29 10:00 大阪单送名古屋 10座 1700",
    "3.29 14:10 关西接机大阪 10座600",
    "3.29 08:00/20:00 环球往返接送 3代600",
    "3.29 08:20 京都送机关西 3代 绿800",
    "3.29 11:25 关西接机大阪 3代 儿童座椅 绿450",
]


def main() -> None:
    init_db(seed=True)
    with get_connection() as conn:
        normalized_locations = {
            "关西": normalize_location_text(conn, "关西"),
            "关空": normalize_location_text(conn, "关空"),
            "KIX": normalize_location_text(conn, "KIX"),
            "关西机场": normalize_location_text(conn, "关西机场"),
            "大阪": normalize_location_text(conn, "大阪"),
            "大阪市内": normalize_location_text(conn, "大阪市内"),
            "Osaka": normalize_location_text(conn, "Osaka"),
        }
        location_count = conn.execute("SELECT COUNT(*) AS c FROM locations").fetchone()["c"]

    parsed = [parse_chinese_order(text) for text in CHARTER_SAMPLES + TRANSFER_SAMPLES]
    drafts = [parse_text_to_draft(text) for text in CHARTER_SAMPLES[:2] + TRANSFER_SAMPLES[:2]]
    failed = parse_text_to_draft("完全无法识别但必须保留的自由文本")

    result = {
        "location_count": location_count,
        "normalized_locations": normalized_locations,
        "date_rules": {
            "3.29": normalize_date_token("3.29"),
            "5.09": normalize_date_token("5.09"),
            "260530": normalize_date_token("260530"),
        },
        "time_rules": {
            "1030": normalize_time_token("1030"),
            "10:30": normalize_time_token("10:30"),
        },
        "parsed_samples": parsed,
        "created_draft_count": len(drafts),
        "failed_status": failed.get("parse_status"),
        "failed_raw_text_kept": failed.get("raw_text") == "完全无法识别但必须保留的自由文本",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
