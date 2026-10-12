from __future__ import annotations

import hashlib
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://api-trial.taxi-airport.jp"
EVIDENCE_DIR = ROOT / "release" / "tourflow-trial-phase2c2r2-fontfix-20261011-r1" / "evidence"
RAW_SIX = """10/9 李力 7495
1️⃣09:30 大阪送机关西 WhatsApp*代收13000日元
2️⃣10:40 关西举牌接机大阪 指定时间 微信
3️⃣13:00 大阪送机关西 微信
4️⃣14:00 关西举牌接机大阪 line
5️⃣17:00 大阪送机关西 微信
6️⃣18:00 关西举牌接机大阪 指定时间 微信"""


class ApiError(RuntimeError):
    pass


def request(method: str, path: str, payload: dict[str, Any] | None = None, token: str = "") -> tuple[int, Any, dict[str, str]]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"User-Agent": "tourflow-r2-fontfix-verifier/1.0"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE_URL + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            body = response.read()
            response_headers = {key.lower(): value for key, value in response.headers.items()}
            if "application/pdf" in response_headers.get("content-type", ""):
                return response.status, body, response_headers
            return response.status, json.loads(body.decode("utf-8")), response_headers
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ApiError(f"{method} {path} -> HTTP {exc.code}: {body}") from exc


def pdf_facts(path: Path) -> dict[str, Any]:
    reader = PdfReader(str(path))
    fonts: set[str] = set()
    embedded = 0
    text_parts: list[str] = []
    for page in reader.pages:
        text_parts.append(page.extract_text() or "")
        resources = page.get("/Resources") or {}
        font_dict = resources.get("/Font") or {}
        for font_ref in font_dict.values():
            font = font_ref.get_object()
            fonts.add(str(font.get("/BaseFont") or ""))
            descriptor = font.get("/FontDescriptor")
            if descriptor:
                desc = descriptor.get_object()
                if any(desc.get(key) is not None for key in ("/FontFile", "/FontFile2", "/FontFile3")):
                    embedded += 1
    text = "\n".join(text_parts)
    return {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size": path.stat().st_size,
        "page_count": len(reader.pages),
        "base_fonts": sorted(fonts),
        "embedded_font_references": embedded,
        "contains_0830": "08:30" in text,
        "contains_2000": "20:00" in text,
        "contains_generic_osaka_hotel": "大阪市内ホテル" in text,
        "contains_spi_name": "氏名：SPI" in text or "氏名:SPI" in text,
        "contains_acceptance": "運送引受書" in text,
        "contains_instruction": "運行指示書" in "".join(text.split()),
    }


def save_pdf(token: str, document: dict[str, Any], file_name: str) -> tuple[Path, dict[str, Any]]:
    status, body, headers = request("GET", f"/api/run-documents/file?document_id={int(document['id'])}", token=token)
    if status != 200 or not isinstance(body, bytes):
        raise ApiError(f"document download failed: status={status}")
    if "application/pdf" not in headers.get("content-type", ""):
        raise ApiError(f"unexpected document content type: {headers.get('content-type')}")
    path = EVIDENCE_DIR / file_name
    path.write_bytes(body)
    return path, pdf_facts(path)


def main() -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    evidence: dict[str, Any] = {"base_url": BASE_URL, "writes_are_trial_test_only": True}

    _, login, _ = request(
        "POST",
        "/api/auth/login-phone",
        {"phone": "08070010000", "password": "010000", "client_type": "web"},
    )
    token = str(login.get("token") or "")
    if not token:
        raise ApiError("authenticated Trial login did not return a token")
    user = login.get("user") or {}
    if int(user.get("tenant_id") or 0) != 88 or str(user.get("role") or "") != "admin":
        raise ApiError(f"unexpected test principal: role={user.get('role')} tenant={user.get('tenant_id')}")
    evidence["principal"] = {"role": user.get("role"), "tenant_id": user.get("tenant_id")}

    _, drivers_payload, _ = request("GET", "/api/dispatch-mobile/drivers", token=token)
    _, vehicles_payload, _ = request("GET", "/api/dispatch-mobile/vehicles", token=token)
    _, routes_payload, _ = request("GET", "/api/dispatch-mobile/fixed-tour/routes", token=token)
    drivers = drivers_payload.get("drivers") or []
    vehicles = vehicles_payload.get("vehicles") or []
    routes = routes_payload.get("routes") or []
    if not drivers or not vehicles or not routes:
        raise ApiError(f"missing Trial options: drivers={len(drivers)} vehicles={len(vehicles)} routes={len(routes)}")
    driver, vehicle, route = drivers[0], vehicles[0], routes[0]
    evidence["options"] = {
        "driver_count": len(drivers),
        "vehicle_count": len(vehicles),
        "route_count": len(routes),
        "selected_driver_id": driver["id"],
        "selected_vehicle_id": vehicle["id"],
        "selected_route_id": route["id"],
    }

    parse_status, parsed, parse_headers = request(
        "POST",
        "/api/dispatch-mobile/parser/daily",
        {"text": RAW_SIX, "default_year": 2026, "default_date": "2026-10-10"},
        token,
    )
    groups = parsed.get("groups") or []
    if len(groups) != 1 or len(groups[0].get("orders") or []) != 6:
        raise ApiError(f"unexpected parser result: groups={len(groups)} orders={parsed.get('order_count')}")
    parsed_group = groups[0]
    parsed_orders = parsed_group["orders"]
    expected_starts = ["09:30", "10:40", "13:00", "14:00", "17:00", "18:00"]
    expected_ends = ["10:30", "11:40", "14:00", "15:00", "18:00", "19:00"]
    actual_starts = [item["parsed"]["start_time"] for item in parsed_orders]
    actual_ends = [item["parsed"]["end_time"] for item in parsed_orders]
    if parsed_group.get("serviceDate") != "2026-10-09" or actual_starts != expected_starts or actual_ends != expected_ends:
        raise ApiError(f"parser dates/times mismatch: date={parsed_group.get('serviceDate')} starts={actual_starts} ends={actual_ends}")
    hotel_suggestions = [
        item["parsed"].get("pickup_suggested_location") or item["parsed"].get("dropoff_suggested_location")
        for item in parsed_orders
    ]
    if not all(hotel_suggestions):
        raise ApiError(f"city hotel suggestions missing: {hotel_suggestions}")
    evidence["daily_parse"] = {
        "http_status": parse_status,
        "request_id": parse_headers.get("x-request-id"),
        "service_date": parsed_group.get("serviceDate"),
        "source_driver_name": parsed_group.get("driverName"),
        "source_vehicle_code": parsed_group.get("vehicleCode"),
        "order_count": len(parsed_orders),
        "start_times": actual_starts,
        "end_times": actual_ends,
        "end_time_sources": [item["parsed"].get("end_time_source") for item in parsed_orders],
        "hotel_suggestions": hotel_suggestions,
    }

    import_orders = []
    for item in parsed_orders:
        order = dict(item["parsed"])
        order.update(
            {
                "order_date": item["date"],
                "end_date": order.get("end_date") or item["date"],
                "start_time": item["time"],
                "pickup_location": order.get("pickup_location") or "待补",
                "dropoff_location": order.get("dropoff_location") or "待补",
            }
        )
        import_orders.append(order)
    batch_id = "trial-r2-fontfix-20261012-raw-six-v1"
    import_payload = {
        "client_batch_id": batch_id,
        "groups": [
            {
                "client_group_index": 0,
                "service_date": "2026-10-09",
                "driver_id": driver["id"],
                "vehicle_id": vehicle["id"],
                "driver_name": driver.get("name"),
                "vehicle_code": vehicle.get("plate_number"),
                "orders": import_orders,
            }
        ],
    }
    first_status, first_import, first_headers = request("POST", "/api/dispatch-mobile/daily-import/assign", import_payload, token)
    retry_status, retry_import, retry_headers = request("POST", "/api/dispatch-mobile/daily-import/assign", import_payload, token)
    _, batch_status, _ = request(
        "GET",
        "/api/dispatch-mobile/daily-import/status?" + urllib.parse.urlencode({"client_batch_id": batch_id}),
        token=token,
    )
    if int(first_import.get("imported_order_count") or 0) != 6:
        raise ApiError(f"daily import count mismatch: {first_import}")
    if not retry_import.get("idempotent_replay") or retry_import.get("order_ids") != first_import.get("order_ids"):
        raise ApiError("daily import retry was not idempotent")
    if (batch_status.get("batch") or {}).get("status") != "succeeded":
        raise ApiError(f"daily batch status mismatch: {batch_status}")
    evidence["daily_import"] = {
        "first_http_status": first_status,
        "retry_http_status": retry_status,
        "first_request_id": first_headers.get("x-request-id"),
        "retry_request_id": retry_headers.get("x-request-id"),
        "client_batch_id": batch_id,
        "order_ids": first_import.get("order_ids"),
        "assignment_ids": first_import.get("assignment_ids"),
        "imported_order_count": first_import.get("imported_order_count"),
        "idempotent_replay": retry_import.get("idempotent_replay"),
        "business_dates": first_import.get("business_dates"),
        "batch_status": (batch_status.get("batch") or {}).get("status"),
    }

    _, run_groups_payload, _ = request("GET", "/api/dispatch-mobile/run-groups?date=2026-10-09", token=token)
    order_ids = {int(item) for item in first_import.get("order_ids") or []}
    matched_group = None
    for item in run_groups_payload.get("groups") or []:
        group_order_ids = {int(order.get("order_id") or order.get("id") or 0) for order in item.get("orders") or []}
        if order_ids and order_ids.issubset(group_order_ids):
            matched_group = item
            break
    if not matched_group:
        raise ApiError("imported daily group was not readable on 2026-10-09")
    group_key = matched_group["key"]
    _, first_doc_payload, _ = request("POST", "/api/dispatch-mobile/run-documents/generate", {"group_key": group_key}, token)
    _, second_doc_payload, _ = request("POST", "/api/dispatch-mobile/run-documents/generate", {"group_key": group_key}, token)
    document = first_doc_payload["document"]
    retry_document = second_doc_payload["document"]
    if document["id"] != retry_document["id"] or document["document_version_id"] != retry_document["document_version_id"]:
        raise ApiError("unchanged daily document generation created a duplicate version")
    _, preview_payload, _ = request("POST", "/api/dispatch-mobile/run-documents/preview", {"group_key": group_key}, token)
    preview = preview_payload["preview"]
    initial_path, initial_pdf = save_pdf(token, document, "trial-r2-fontfix-daily-six-initial.pdf")
    if initial_pdf["page_count"] != 3:
        raise ApiError(f"daily packet page count mismatch: {initial_pdf['page_count']}")
    if not initial_pdf["contains_0830"] or not initial_pdf["contains_2000"]:
        raise ApiError("daily packet is missing 08:30 or 20:00")
    if initial_pdf["contains_generic_osaka_hotel"] or initial_pdf["contains_spi_name"]:
        raise ApiError("daily packet retained generic Osaka hotel or unsupported SPI fallback")
    evidence["daily_document_initial"] = {
        "group_key": group_key,
        "document_id": document.get("document_id"),
        "document_version_id": document.get("document_version_id"),
        "row_id": document.get("id"),
        "version": document.get("version"),
        "renderer_version": document.get("renderer_version"),
        "page_count": document.get("page_count"),
        "source_sha256": document.get("source_sha256"),
        "server_pdf_sha256": document.get("pdf_sha256"),
        "download_path": str(initial_path),
        "pdf": initial_pdf,
        "validation_issue_count": len(preview.get("validation_issues") or []),
        "node_count": len(preview.get("nodes") or []),
    }

    pickup_node = next((node for node in preview.get("nodes") or [] if node.get("node_type") == "pickup"), None)
    if not pickup_node:
        raise ApiError("daily preview did not expose an editable pickup node")
    original_node_id = pickup_node["route_node_id"]
    edited_location = str(pickup_node.get("planned_location") or "").rstrip() + "（R2核验）"
    _, edit_payload, _ = request(
        "POST",
        "/api/dispatch-mobile/run-documents/node",
        {
            "group_key": group_key,
            "route_node_id": original_node_id,
            "planned_location": edited_location,
            "planned_departure_at": pickup_node.get("planned_departure_at"),
        },
        token,
    )
    edited_preview = edit_payload["preview"]
    edited_node = next(node for node in edited_preview.get("nodes") or [] if node.get("route_node_id") == original_node_id)
    if edited_node.get("planned_location") != edited_location:
        raise ApiError("edited daily route node was not preserved")
    _, replacement_payload, _ = request("POST", "/api/dispatch-mobile/run-documents/generate", {"group_key": group_key}, token)
    replacement = replacement_payload["document"]
    _, replacement_retry_payload, _ = request("POST", "/api/dispatch-mobile/run-documents/generate", {"group_key": group_key}, token)
    replacement_retry = replacement_retry_payload["document"]
    if replacement["id"] == document["id"] or replacement_retry["id"] != replacement["id"]:
        raise ApiError("node edit did not create exactly one replacement document version")
    replacement_path, replacement_pdf = save_pdf(token, replacement, "trial-r2-fontfix-daily-six-edited.pdf")
    evidence["daily_node_edit"] = {
        "route_node_id_before": original_node_id,
        "route_node_id_after": edited_node.get("route_node_id"),
        "planned_location": edited_location,
        "replacement_document_id": replacement.get("document_id"),
        "replacement_version_id": replacement.get("document_version_id"),
        "replacement_version": replacement.get("version"),
        "retry_same_row_id": replacement_retry.get("id") == replacement.get("id"),
        "download_path": str(replacement_path),
        "pdf": replacement_pdf,
    }

    charter_date = "2026-11-12"
    draft_request_id = "trial-r2-fontfix-20261012-charter-v1"
    draft_status, draft_payload, _ = request(
        "POST",
        "/api/dispatch-mobile/fixed-tour/drafts",
        {
            "client_request_id": draft_request_id,
            "source_preset_id": route["id"],
            "business_start_date": charter_date,
        },
        token,
    )
    _, draft_retry_payload, _ = request(
        "POST",
        "/api/dispatch-mobile/fixed-tour/drafts",
        {
            "client_request_id": draft_request_id,
            "source_preset_id": route["id"],
            "business_start_date": charter_date,
        },
        token,
    )
    draft = draft_payload["draft"]
    if draft_retry_payload["draft"]["id"] != draft["id"]:
        raise ApiError("charter draft retry created a duplicate")
    draft_id = draft["id"]
    _, charter_first, _ = request(
        "POST",
        f"/api/dispatch-mobile/fixed-tour/drafts/{draft_id}/generate-documents",
        {"driver_id": driver["id"], "vehicle_id": vehicle["id"]},
        token,
    )
    _, charter_retry, _ = request(
        "POST",
        f"/api/dispatch-mobile/fixed-tour/drafts/{draft_id}/generate-documents",
        {"driver_id": driver["id"], "vehicle_id": vehicle["id"]},
        token,
    )
    charter_doc = charter_first["document"]
    if charter_retry["document"]["id"] != charter_doc["id"] or not charter_retry["assignment"].get("reused"):
        raise ApiError("charter generation retry was not idempotent")
    charter_path, charter_pdf = save_pdf(token, charter_doc, "trial-r2-fontfix-charter.pdf")
    if charter_pdf["page_count"] != 2:
        raise ApiError(f"charter packet page count mismatch: {charter_pdf['page_count']}")
    evidence["charter"] = {
        "draft_http_status": draft_status,
        "client_request_id": draft_request_id,
        "draft_id": draft_id,
        "order_id": draft.get("order_id"),
        "assignment_ids": charter_first["assignment"].get("assignment_ids"),
        "assignment_reused_on_retry": charter_retry["assignment"].get("reused"),
        "document_id": charter_doc.get("document_id"),
        "document_version_id": charter_doc.get("document_version_id"),
        "row_id": charter_doc.get("id"),
        "version": charter_doc.get("version"),
        "renderer_version": charter_doc.get("renderer_version"),
        "page_count": charter_doc.get("page_count"),
        "source_sha256": charter_doc.get("source_sha256"),
        "server_pdf_sha256": charter_doc.get("pdf_sha256"),
        "download_path": str(charter_path),
        "pdf": charter_pdf,
    }

    evidence_path = EVIDENCE_DIR / "trial-r2-fontfix-authenticated-integration.json"
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "evidence": str(evidence_path),
        "daily_order_ids": evidence["daily_import"]["order_ids"],
        "daily_assignment_ids": evidence["daily_import"]["assignment_ids"],
        "daily_initial_pdf": initial_pdf,
        "daily_edited_pdf": replacement_pdf,
        "charter_pdf": charter_pdf,
        "daily_document": {
            "initial_row_id": document["id"],
            "edited_row_id": replacement["id"],
            "idempotent_retry": replacement_retry["id"] == replacement["id"],
        },
        "charter": {
            "draft_id": draft_id,
            "document_row_id": charter_doc["id"],
            "idempotent_retry": charter_retry["document"]["id"] == charter_doc["id"],
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        raise
