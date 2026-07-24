from __future__ import annotations

import base64
import csv
import json
import os
import re
import uuid
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote, unquote, urljoin
from urllib.request import Request, urlopen


DEFAULT_LIBRARY_ROOT = Path("/var/www/tourflow-admin/vehicle-docs") if os.name != "nt" else Path(r"C:\Pang.S\车辆资料整理")
DEFAULT_LIBRARY_BASE_URL = "https://admin-trial.taxi-airport.jp/vehicle-docs/"


def _library_base_url() -> str:
    raw = os.environ.get("DISPATCH_RESOURCE_LIBRARY_BASE_URL", "").strip()
    if raw:
        return raw.rstrip("/") + "/"
    if not _library_root().exists():
        return DEFAULT_LIBRARY_BASE_URL
    return ""


def _library_root() -> Path:
    return Path(os.environ.get("DISPATCH_RESOURCE_LIBRARY_ROOT") or DEFAULT_LIBRARY_ROOT)


def _server_demo_root() -> Path:
    return _library_root() / "server_demo"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8")


def _read_url_text(url: str) -> str:
    headers = {"User-Agent": "TourDispatchResourceBridge/1.0"}
    basic_auth = os.environ.get("DISPATCH_RESOURCE_LIBRARY_BASIC_AUTH", "").strip()
    if basic_auth:
        encoded = base64.b64encode(basic_auth.encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {encoded}"
    bearer = os.environ.get("DISPATCH_RESOURCE_LIBRARY_BEARER_TOKEN", "").strip()
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=12) as response:
        raw = response.read()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("utf-8")


def _read_source_text(relative_path: str) -> str:
    base_url = _library_base_url()
    if base_url:
        return _read_url_text(urljoin(base_url, quote(relative_path, safe="/")))
    return _read_text(_library_root() / relative_path)


def _extract_vehicle_payload() -> list[dict]:
    try:
        html = _read_source_text("index.html")
    except (OSError, ValueError):
        try:
            html = _read_text(_server_demo_root() / "index.html")
        except OSError:
            return []
    match = re.search(r"const\s+(?:DATA|vehicles)\s*=\s*(\[.*?\]);\s*\n", html, re.DOTALL)
    if not match:
        return []
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return []


def _read_csv_rows(filename: str) -> list[dict]:
    try:
        text = _read_source_text(filename)
    except (OSError, ValueError):
        return []
    return [dict(row) for row in csv.DictReader(text.splitlines())]


def _digits(value: str | None) -> str:
    return "".join(re.findall(r"\d+", value or ""))


def _plate_suffix(value: str | None) -> str:
    suffix = _digits(value)[-4:]
    return str(int(suffix)) if suffix else ""


def _size_label(size: int | str | None) -> str:
    try:
        value = int(size or 0)
    except (TypeError, ValueError):
        return ""
    if value >= 1024 * 1024:
        return f"{value / 1024 / 1024:.1f}MB"
    if value >= 1024:
        return f"{value / 1024:.0f}KB"
    return f"{value}B" if value else ""


def _file_download_path(file_key: str) -> str:
    base_url = _library_base_url()
    if base_url:
        return urljoin(base_url, file_key)
    return f"/api/dispatch-mobile/resource-library/file?file={quote(file_key, safe='')}"


def _vehicle_updates_path() -> Path:
    return _library_root() / "mobile_vehicle_inspection_updates.json"


def _load_vehicle_inspection_updates() -> dict:
    path = _vehicle_updates_path()
    if not path.exists():
        return {}
    try:
        return json.loads(_read_text(path))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_vehicle_inspection_updates(data: dict) -> None:
    path = _vehicle_updates_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv_rows(filename: str, rows: list[dict], fields: list[str]) -> None:
    import io

    path = _library_root() / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_name(f"{path.name}.bak-status-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        backup.write_bytes(path.read_bytes())
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text("\ufeff" + buffer.getvalue(), encoding="utf-8")


def _first(row: dict, *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _current_online_driver_table(rows: list[dict]) -> list[dict]:
    """Apply the current online roster state to the older local CSV snapshot."""
    if not rows:
        return rows
    fields = list(rows[0])
    if len(fields) < 15:
        return rows
    id_key, name_key, license_key, license_number_key = fields[1], fields[3], fields[4], fields[5]
    residence_status_key, residence_due_key = fields[6], fields[7]
    phone_key, status_key = fields[10], fields[13]
    current_codes = {
        "周政": "12361",
        "叢枝佳": "kyoto-1",
        "林澤群": "kyoto-2",
        "矢口萱": "kyoto-3",
        "董星": "kyoto-4",
        "刘晓丽": "12363",
        "权永住": "12365",
        "菜卫平": "12360",
    }
    current_overrides = {
        "刘晓丽": ("080-4647-1999", "2028-03-25", "621606948020", "永住者", "2027-02-17"),
        "权永住": ("080-3106-9666", "2029-01-27", "621104983445", "永住者", "2031-12-09"),
        "菜卫平": ("060-6971-8890", "2027-06-27", "621103645000", "日本の国籍", ""),
    }
    result = []
    for original in rows:
        row = dict(original)
        name = str(row.get(name_key) or "").strip()
        if name == "王爽":
            row[status_key] = "离职"
        if name in current_codes:
            row[id_key] = current_codes[name]
        if name in current_overrides:
            phone, license_due, license_number, residence_status, residence_due = current_overrides[name]
            row[phone_key] = phone
            row[license_key] = license_due
            row[license_number_key] = license_number
            row[residence_status_key] = residence_status
            row[residence_due_key] = residence_due
        result.append(row)
    return result


def list_resource_library() -> dict:
    vehicle_table = _read_csv_rows("车辆信息总表.csv")
    driver_table = _read_csv_rows("司机信息表.csv")
    driver_table = _current_online_driver_table(driver_table)
    vehicle_updates = _load_vehicle_inspection_updates()
    vehicle_meta_by_suffix = {
        _plate_suffix(_first(row, "后四位", "车牌号", "车辆ナンバー", "車両ナンバー")): row
        for row in vehicle_table
        if _digits(_first(row, "后四位", "车牌号", "车辆ナンバー", "車両ナンバー"))
    }
    vehicles = []
    categories = set()
    total_files = 0

    for item in _extract_vehicle_payload():
        suffix = _plate_suffix(item.get("suffix") or item.get("plate"))
        meta = vehicle_meta_by_suffix.get(suffix, {})
        files = []
        for pdf in item.get("files") or []:
            file_key = str(pdf.get("href") or "")
            if not file_key:
                continue
            category = str(pdf.get("category") or "其他")
            categories.add(category)
            files.append({
                "name": pdf.get("name") or Path(file_key).name,
                "category": category,
                "date": pdf.get("date") or "",
                "size": pdf.get("size") or 0,
                "size_label": _size_label(pdf.get("size")),
                "file_key": file_key,
                "download_path": _file_download_path(file_key),
                "download_url": _file_download_path(file_key),
            })
        update = vehicle_updates.get(suffix, {})
        for doc in update.get("docs", []):
            file_key = str(doc.get("file_key") or "")
            if not file_key:
                continue
            category = str(doc.get("category") or "车辆资料")
            categories.add(category)
            files.append({
                "name": doc.get("file_name") or Path(file_key).name,
                "category": category,
                "date": doc.get("date") or "",
                "size": doc.get("file_size") or 0,
                "size_label": _size_label(doc.get("file_size")),
                "file_key": file_key,
                "download_path": _file_download_path(file_key),
                "download_url": _file_download_path(file_key),
            })
        total_files += len(files)
        vehicles.append({
            "id": item.get("folder") or suffix or item.get("plate"),
            "plate_number": _first(meta, "车牌号", "车辆ナンバー", "車両ナンバー") or item.get("plate") or "",
            "suffix": suffix,
            "chassis_number": _first(meta, "车台番号", "車両ナンバー") or item.get("chassis") or "",
            "model_code": _first(meta, "型式") or "",
            "vehicle_type": _first(meta, "车型", "車種名") or "",
            "vehicle_inspection_due_date": _first(meta, "车检到期", "車検満了日") or "",
            "shaken_date": update.get("vehicle_inspection_date") or _first(meta, "車検日期", "車検") or "",
            "three_month_inspection_date": update.get("three_month_inspection_date") or _first(meta, "3ヶ月点検日期", "三か月点検") or "",
            "annual_inspection_date": _first(meta, "12ヶ月点検日期", "12ヶ月点検日") or "",
            "status": update.get("status") or _first(meta, "status", "vehicle_status") or "available",
            "folder": item.get("folder") or "",
            "file_count": len(files),
            "categories": item.get("categories") or sorted({file["category"] for file in files}),
            "docs": files,
        })

    return {
        "source": "url" if _library_base_url() else "local",
        "root_available": bool(_library_base_url()) or _server_demo_root().exists(),
        "summary": {
            "vehicles": len(vehicles) or len(vehicle_table),
            "drivers": len(driver_table),
            "pdf_files": total_files,
            "categories": len(categories),
        },
        "vehicles": vehicles,
        "drivers": driver_table,
        "categories": sorted(categories),
    }


def _parse_iso_date(value: str) -> date:
    try:
        return datetime.strptime(str(value or "").strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("invalid_health_check_date") from exc


def _add_one_year(value: date) -> date:
    try:
        return value.replace(year=value.year + 1)
    except ValueError:
        return value.replace(year=value.year + 1, day=28)


def _health_status(days_remaining: int) -> str:
    if days_remaining < 0:
        return "expired"
    if days_remaining <= 30:
        return "watch"
    return "ok"


def _decode_upload_payload(value: str) -> bytes:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("missing_health_document")
    match = re.match(r"^data:[^;]+;base64,(.+)$", raw, re.IGNORECASE | re.DOTALL)
    if match:
        raw = match.group(1)
    try:
        data = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ValueError("invalid_health_document") from exc
    if len(data) < 16:
        raise ValueError("health_document_too_small")
    if len(data) > 12 * 1024 * 1024:
        raise ValueError("health_document_too_large")
    return data


def _safe_upload_ext(file_name: str, content_type: str = "") -> str:
    suffix = Path(str(file_name or "")).suffix.lower().lstrip(".")
    content_type = str(content_type or "").lower()
    if not suffix:
        if "pdf" in content_type:
            suffix = "pdf"
        elif "png" in content_type:
            suffix = "png"
        elif "webp" in content_type:
            suffix = "webp"
        else:
            suffix = "jpg"
    if suffix in {"jpeg", "jpg", "png", "webp", "pdf"}:
        return "jpg" if suffix == "jpeg" else suffix
    raise ValueError("unsupported_health_document_type")


def _save_driver_health_document(driver_key: str, health_check_date: str, payload: dict | None) -> dict:
    payload = payload or {}
    file_data = str(payload.get("file_base64") or payload.get("document_base64") or payload.get("image_base64") or "").strip()
    if not file_data:
        return {}
    data = _decode_upload_payload(file_data)
    file_name = str(payload.get("file_name") or "health-check").strip()
    suffix = _safe_upload_ext(file_name, payload.get("content_type") or "")
    safe_driver = re.sub(r"[^A-Za-z0-9_-]+", "_", str(driver_key or "driver")).strip("_") or "driver"
    safe_date = re.sub(r"[^0-9-]+", "", str(health_check_date or "")) or date.today().isoformat()
    stored_name = f"{safe_driver}_{safe_date}_{uuid.uuid4().hex[:8]}.{suffix}"
    folder = _library_root() / "driver-health"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / stored_name
    target.write_bytes(data)
    return {
        "file_key": f"driver-health/{stored_name}",
        "file_name": file_name or stored_name,
        "file_size": len(data),
    }


def update_driver_health_check_date(driver_key: str, health_check_date: str, payload: dict | None = None) -> dict:
    key = str(driver_key or "").strip()
    if not key:
        raise ValueError("driver_key_required")
    exam_date = _parse_iso_date(health_check_date)
    due_date = _add_one_year(exam_date)
    days_remaining = (due_date - date.today()).days
    status = _health_status(days_remaining)
    root = _library_root()
    path = root / "司机信息表.csv"
    if not path.exists():
        raise ValueError("driver_resource_not_found")
    rows = _current_online_driver_table(_read_csv_rows("司机信息表.csv"))
    if not rows:
        raise ValueError("driver_resource_empty")
    fields = list(rows[0].keys())
    name_keys = ("運転手名", "司机姓名", "姓名", "name", "driver_name")
    code_keys = ("運転手ID", "司机编号", "driver_code", "code", "序号")
    phone_keys = ("携帯電話番号", "电话", "phone")
    normalized_key = _digits(key) if re.fullmatch(r"[\d\s()+-]+", key) else key
    target = None
    for row in rows:
        candidates = []
        for candidate_key in (*name_keys, *code_keys, *phone_keys):
            value = _first(row, candidate_key)
            if value:
                candidates.append(value)
                digits = _digits(value)
                if digits:
                    candidates.append(digits)
        if key in candidates or normalized_key in candidates:
            target = row
            break
    if target is None:
        raise ValueError("driver_not_found")
    document = _save_driver_health_document(_first(target, *code_keys) or key, exam_date.isoformat(), payload)
    for extra_field in ("健康诊断资料", "健康诊断资料文件名", "健康诊断资料上传时间"):
        if extra_field not in fields:
            fields.append(extra_field)
    target["健康诊断日期"] = exam_date.isoformat()
    target["健康诊断剩余有效天数"] = str(days_remaining)
    target["健康诊断日期_状态"] = status
    target["健康诊断状态"] = status
    if document:
        target["健康诊断资料"] = document["file_key"]
        target["健康诊断资料文件名"] = document["file_name"]
        target["健康诊断资料上传时间"] = datetime.now().isoformat(timespec="seconds")
    import io

    backup = path.with_name(f"{path.name}.bak-health-{datetime.now().strftime('%Y%m%d%H%M%S')}")
    backup.write_bytes(path.read_bytes())
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text("\ufeff" + buffer.getvalue(), encoding="utf-8")
    return {
        "driver": target,
        "health_check_date": exam_date.isoformat(),
        "health_due_date": due_date.isoformat(),
        "days_remaining": days_remaining,
        "status": status,
        "document": document,
    }


def update_driver_resource_status(driver_key: str, status: str, payload: dict | None = None) -> dict:
    key = str(driver_key or "").strip()
    if not key:
        raise ValueError("driver_key_required")
    normalized_status = str(status or "").strip() or "available"
    rows = _current_online_driver_table(_read_csv_rows("司机信息表.csv"))
    if not rows:
        raise ValueError("driver_resource_empty")
    fields = list(rows[0].keys())
    name_keys = ("運転手名", "司机姓名", "姓名", "name", "driver_name")
    code_keys = ("運転手ID", "司机编号", "driver_code", "code", "序号")
    phone_keys = ("携帯電話番号", "电话", "phone")
    normalized_key = _digits(key) if re.fullmatch(r"[\d\s()+-]+", key) else key
    target = None
    for row in rows:
        candidates = []
        for candidate_key in (*name_keys, *code_keys, *phone_keys):
            value = _first(row, candidate_key)
            if value:
                candidates.append(value)
                normalized = _digits(value)
                if normalized:
                    candidates.append(normalized)
        if key in candidates or normalized_key in candidates:
            target = row
            break
    if target is None:
        raise ValueError("driver_not_found")
    for extra_field in ("状態", "状态", "driver_status", "status", "资料更新时间"):
        if extra_field not in fields:
            fields.append(extra_field)
    target["状態"] = normalized_status
    target["状态"] = normalized_status
    target["driver_status"] = normalized_status
    target["status"] = normalized_status
    target["资料更新时间"] = datetime.now().isoformat(timespec="seconds")
    _write_csv_rows("司机信息表.csv", rows, fields)
    return {"driver": target, "status": normalized_status}


def update_vehicle_resource_status(vehicle_key: str, status: str, payload: dict | None = None) -> dict:
    key = str(vehicle_key or "").strip()
    suffix = _plate_suffix(key) or key
    if not suffix:
        raise ValueError("vehicle_key_required")
    normalized_status = str(status or "").strip() or "available"
    if normalized_status not in {"available", "maintenance", "retired"}:
        raise ValueError("invalid_vehicle_status")
    updates = _load_vehicle_inspection_updates()
    target = updates.setdefault(suffix, {"docs": []})
    target["status"] = normalized_status
    target["status_updated_at"] = datetime.now().isoformat(timespec="seconds")
    _write_vehicle_inspection_updates(updates)
    return {"vehicle_key": suffix, "status": normalized_status, "vehicle": target}


def _save_vehicle_inspection_document(vehicle_key: str, inspection_type: str, inspection_date: str, payload: dict | None) -> dict:
    payload = payload or {}
    file_data = str(payload.get("file_base64") or payload.get("document_base64") or payload.get("image_base64") or "").strip()
    if not file_data:
        return {}
    data = _decode_upload_payload(file_data)
    file_name = str(payload.get("file_name") or "vehicle-inspection").strip()
    suffix = _safe_upload_ext(file_name, payload.get("content_type") or "")
    safe_vehicle = re.sub(r"[^A-Za-z0-9_-]+", "_", str(vehicle_key or "vehicle")).strip("_") or "vehicle"
    safe_type = "vehicle" if inspection_type == "vehicle" else "inspection"
    safe_date = re.sub(r"[^0-9-]+", "", str(inspection_date or "")) or date.today().isoformat()
    stored_name = f"{safe_vehicle}_{safe_type}_{safe_date}_{uuid.uuid4().hex[:8]}.{suffix}"
    folder = _library_root() / "mobile-vehicle-inspections"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / stored_name
    target.write_bytes(data)
    return {
        "file_key": f"mobile-vehicle-inspections/{stored_name}",
        "file_name": file_name or stored_name,
        "file_size": len(data),
    }


def upload_vehicle_resource_document(vehicle_key: str, category: str, document_date: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    key = str(vehicle_key or "").strip()
    suffix = _plate_suffix(key) or key
    if not suffix:
        raise ValueError("vehicle_key_required")
    normalized_category = str(category or "").strip()
    if not normalized_category:
        raise ValueError("resource_category_required")
    file_data = str(payload.get("file_base64") or payload.get("document_base64") or "").strip()
    if not file_data:
        raise ValueError("resource_document_required")
    data = _decode_upload_payload(file_data)
    if not data.startswith(b"%PDF-"):
        raise ValueError("resource_document_must_be_pdf")
    original_name = str(payload.get("file_name") or "vehicle-resource.pdf").strip()
    custom_title = str(payload.get("custom_title") or payload.get("title") or "").strip()
    display_name = custom_title or original_name
    if not display_name.lower().endswith(".pdf"):
        display_name = f"{display_name}.pdf"
    safe_vehicle = re.sub(r"[^A-Za-z0-9_-]+", "_", suffix).strip("_") or "vehicle"
    stored_name = f"{safe_vehicle}_{uuid.uuid4().hex[:12]}.pdf"
    folder = _library_root() / "mobile-resource-library" / safe_vehicle
    folder.mkdir(parents=True, exist_ok=True)
    target_path = folder / stored_name
    target_path.write_bytes(data)
    document = {
        "file_key": f"mobile-resource-library/{safe_vehicle}/{stored_name}",
        "file_name": display_name,
        "file_size": len(data),
        "category": normalized_category,
        "date": str(document_date or "").strip(),
        "uploaded_at": datetime.now().isoformat(timespec="seconds"),
    }
    updates = _load_vehicle_inspection_updates()
    target = updates.setdefault(suffix, {"docs": []})
    target.setdefault("docs", []).append(document)
    _write_vehicle_inspection_updates(updates)
    return {"vehicle_key": suffix, "document": document}


def update_vehicle_inspection_date(vehicle_key: str, inspection_type: str, inspection_date: str, payload: dict | None = None) -> dict:
    key = str(vehicle_key or "").strip()
    if not key:
        raise ValueError("vehicle_key_required")
    record_date = _parse_iso_date(inspection_date)
    normalized_type = "vehicle" if str(inspection_type or "").lower() in {"vehicle", "shaken", "annual", "car_check"} else "inspection"
    suffix = _plate_suffix(key) or key
    if not suffix:
        raise ValueError("vehicle_key_required")
    updates = _load_vehicle_inspection_updates()
    target = updates.setdefault(suffix, {"docs": []})
    date_key = "vehicle_inspection_date" if normalized_type == "vehicle" else "three_month_inspection_date"
    target[date_key] = record_date.isoformat()
    document = _save_vehicle_inspection_document(suffix, normalized_type, record_date.isoformat(), payload)
    if document:
        category = "车检" if normalized_type == "vehicle" else "3ヶ月点検"
        target.setdefault("docs", []).append({
            **document,
            "category": category,
            "date": record_date.isoformat(),
            "inspection_type": normalized_type,
            "uploaded_at": datetime.now().isoformat(timespec="seconds"),
        })
    _write_vehicle_inspection_updates(updates)
    return {
        "vehicle_key": suffix,
        "inspection_type": normalized_type,
        "inspection_date": record_date.isoformat(),
        "document": document,
    }


def resolve_resource_pdf(file_key: str) -> Path | None:
    if _library_base_url():
        return None
    if not file_key or "\\" in file_key:
        return None
    relative = unquote(file_key).lstrip("/").replace("/", os.sep)
    for root_path in (_library_root(), _server_demo_root()):
        target = root_path / relative
        try:
            resolved = target.resolve()
            root = root_path.resolve()
        except OSError:
            continue
        if str(resolved).startswith(str(root)) and resolved.suffix.lower() == ".pdf" and resolved.is_file():
            return resolved
    return None
