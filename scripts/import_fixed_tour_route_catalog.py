from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "runtime" / "wx_dispatch.sqlite3"
DEFAULT_CATALOG = ROOT / "backend" / "assets" / "fixed_tour_route_catalog.json"

ROUTE_FIELDS = (
    "route_code",
    "route_name",
    "status",
    "default_start_time",
    "default_end_time",
    "standard_duration_minutes",
    "operations_business_area",
    "default_order_type",
    "route_summary",
    "document_remark",
    "application_method",
    "applicant_name",
    "contact_name",
    "contact_phone",
)


def load_catalog(path: Path = DEFAULT_CATALOG) -> list[dict[str, Any]]:
    routes = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(routes, list) or not routes:
        raise ValueError("fixed_tour_catalog_empty")
    codes: set[str] = set()
    for route in routes:
        code = str(route.get("route_code") or "").strip()
        name = str(route.get("route_name") or "").strip()
        stops = route.get("stops") or []
        if not code or not name or len(stops) < 2:
            raise ValueError(f"fixed_tour_catalog_invalid:{code or name or 'unknown'}")
        if code in codes:
            raise ValueError(f"fixed_tour_catalog_duplicate_code:{code}")
        if route.get("status") != "active":
            raise ValueError(f"fixed_tour_catalog_route_must_be_visible:{code}")
        codes.add(code)
    return routes


def resolve_tenant(
    conn: sqlite3.Connection,
    tenant_id: int | None = None,
    tenant_slug: str | None = None,
) -> sqlite3.Row:
    if tenant_id is not None:
        row = conn.execute("SELECT id, name, slug FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
        if not row:
            raise ValueError(f"tenant_not_found:{tenant_id}")
        return row
    if tenant_slug:
        row = conn.execute(
            "SELECT id, name, slug FROM tenants WHERE lower(slug) = lower(?)",
            (tenant_slug.strip(),),
        ).fetchone()
        if not row:
            raise ValueError(f"tenant_not_found:{tenant_slug}")
        return row
    rows = conn.execute(
        """
        SELECT id, name, slug
        FROM tenants
        WHERE lower(slug) IN ('daitora', 'dtr') OR lower(name) = 'daitora'
        ORDER BY CASE WHEN lower(slug) = 'dtr' THEN 0 ELSE 1 END, id
        """
    ).fetchall()
    if not rows:
        raise ValueError("daitora_tenant_not_found")
    if len(rows) > 1:
        identities = ",".join(f"{row['id']}:{row['slug']}" for row in rows)
        raise ValueError(f"multiple_daitora_tenants:{identities};use_--tenant-id")
    return rows[0]


def import_catalog(
    conn: sqlite3.Connection,
    tenant_id: int,
    routes: list[dict[str, Any]],
    *,
    apply: bool,
) -> dict[str, Any]:
    inserted: list[str] = []
    skipped: list[str] = []
    for route in routes:
        route_code = str(route["route_code"])
        existing = conn.execute(
            "SELECT id FROM fixed_tour_routes WHERE tenant_id = ? AND route_code = ?",
            (tenant_id, route_code),
        ).fetchone()
        if existing:
            skipped.append(route_code)
            continue
        inserted.append(route_code)
        if not apply:
            continue
        values = [route.get(field) for field in ROUTE_FIELDS]
        cursor = conn.execute(
            "INSERT INTO fixed_tour_routes (tenant_id, "
            + ", ".join(ROUTE_FIELDS)
            + ") VALUES (?, "
            + ", ".join("?" for _ in ROUTE_FIELDS)
            + ")",
            (tenant_id, *values),
        )
        route_id = int(cursor.lastrowid)
        stops = route.get("stops") or []
        for sequence_no, stop in enumerate(stops, 1):
            conn.execute(
                """
                INSERT INTO fixed_tour_route_stops (
                    tenant_id, route_id, sequence_no, stop_type, location_name,
                    default_arrival_time, default_departure_time, stay_minutes, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tenant_id,
                    route_id,
                    sequence_no,
                    stop.get("stop_type")
                    or ("pickup" if sequence_no == 1 else "dropoff" if sequence_no == len(stops) else "waypoint"),
                    stop.get("location_name") or "",
                    stop.get("default_arrival_time"),
                    stop.get("default_departure_time"),
                    stop.get("stay_minutes"),
                    stop.get("note"),
                ),
            )
        for price in route.get("prices") or []:
            if price.get("vehicle_type") and price.get("price_jpy") not in (None, ""):
                conn.execute(
                    "INSERT INTO fixed_tour_route_prices (tenant_id, route_id, vehicle_type, price_jpy) VALUES (?, ?, ?, ?)",
                    (tenant_id, route_id, price["vehicle_type"], float(price["price_jpy"])),
                )
    return {
        "tenant_id": tenant_id,
        "catalog_count": len(routes),
        "inserted_count": len(inserted),
        "skipped_count": len(skipped),
        "inserted_route_codes": inserted,
        "skipped_route_codes": skipped,
        "applied": apply,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import the reviewed DAITORA fixed-tour catalog. Existing route codes are preserved."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--tenant-id", type=int)
    parser.add_argument("--tenant-slug")
    parser.add_argument("--apply", action="store_true", help="Write changes. Without this flag the command is a dry run.")
    args = parser.parse_args()

    routes = load_catalog(args.catalog)
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        tenant = resolve_tenant(conn, args.tenant_id, args.tenant_slug)
        result = import_catalog(conn, int(tenant["id"]), routes, apply=args.apply)
        result["tenant_name"] = tenant["name"]
        result["tenant_slug"] = tenant["slug"]
        result["db"] = str(args.db.resolve())
        if args.apply:
            conn.commit()
        else:
            conn.rollback()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
