import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.db.database import get_connection, init_db


BASE_URL = os.environ.get("WX_DISPATCH_BASE_URL", "http://127.0.0.1:18765")
TOKEN = ""
TEST_PNG_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="


def request(method: str, path: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as parse_exc:
            raise RuntimeError(f"{method} {path} failed: {exc.code} {body}") from parse_exc
        payload["_status"] = exc.code
        return payload


def main() -> None:
    global TOKEN
    init_db(seed=True)
    ping = request("GET", "/api/ping")
    login = request("POST", "/api/auth/login", {"username": "admin", "password": "admin123"})
    TOKEN = login["token"]
    suffix = str(int(datetime.now().timestamp()))
    drivers = [
        request("POST", "/api/resources/drivers", {"name": f"R006司机A{suffix}", "phone": f"R006-A-{suffix}", "status": "available"})["driver"],
        request("POST", "/api/resources/drivers", {"name": f"R006司机B{suffix}", "phone": f"R006-B-{suffix}", "status": "available"})["driver"],
    ]
    vehicles = [
        request("POST", "/api/resources/vehicles", {"plate_number": f"R006{suffix}", "vehicle_type": "商务车", "seat_count": 6, "status": "available"})["vehicle"]
    ]
    driver_id = drivers[0]["id"]
    other_driver_id = drivers[1]["id"]
    vehicle_id = vehicles[0]["id"]

    base_minute = 480 + (int(datetime.now().timestamp()) % 360)
    order = request(
        "POST",
        "/api/orders",
        {
            "order_date": date.today().isoformat(),
            "start_time": _format_time(base_minute),
            "end_time": _format_time(base_minute + 60),
            "pickup_location": "司机端测试起点",
            "dropoff_location": "司机端测试终点",
            "order_type": "接机",
            "vehicle_type": "商务车",
            "passenger_count": 2,
            "luggage_count": 1,
            "guest_name": "司机端客人",
            "guest_contact": "09011112222",
            "agency_name": "R006测试旅行社",
            "price": 25000,
            "remark": "R006 driver smoke",
        },
    )["order"]
    assigned = request("POST", "/api/dispatch/assign", {"order_ids": [order["id"]], "driver_id": driver_id, "vehicle_id": vehicle_id})
    if not assigned.get("success"):
        raise RuntimeError(f"assign failed: {assigned}")
    assignment_id = assigned["assignment_ids"][0]
    next_order = request(
        "POST",
        "/api/orders",
        {
            "order_date": date.today().isoformat(),
            "start_time": _format_time(base_minute + 90),
            "end_time": _format_time(base_minute + 150),
            "pickup_location": "verify next pickup",
            "dropoff_location": "verify next dropoff",
            "order_type": "charter",
            "vehicle_type": "business",
            "passenger_count": 3,
            "luggage_count": 2,
            "guest_name": "verify next guest",
            "guest_contact": "09033334444",
            "agency_name": "verify agency",
            "price": 18000,
            "remark": "R044 next order smoke",
        },
    )["order"]
    next_assigned = request("POST", "/api/dispatch/assign", {"order_ids": [next_order["id"]], "driver_id": driver_id, "vehicle_id": vehicle_id})
    if not next_assigned.get("success"):
        raise RuntimeError(f"next assign failed: {next_assigned}")
    next_assignment_id = next_assigned["assignment_ids"][0]
    driver_notifications = request("GET", f"/api/driver/notifications?driver_id={driver_id}")["notifications"]
    new_order_notifications = [item for item in driver_notifications if item.get("notification_type") == "new_order"]
    first_notification_id = new_order_notifications[0]["id"] if new_order_notifications else None
    notification_read = (
        request("POST", f"/api/driver/notifications/{first_notification_id}/read", {"driver_id": driver_id})
        if first_notification_id
        else {}
    )
    driver_notifications_after_read = request("GET", f"/api/driver/notifications?driver_id={driver_id}")["notifications"]

    own_assignments = request("GET", f"/api/driver/assignments?driver_id={driver_id}")["assignments"]
    detail = request("GET", f"/api/driver/assignments/{assignment_id}?driver_id={driver_id}")["assignment"]
    other_detail = request("GET", f"/api/driver/assignments/{assignment_id}?driver_id={other_driver_id}")
    public_detail = request("GET", f"/api/driver/assignments/{assignment_id}?driver_id={driver_id}")
    workbench_initial = request("GET", f"/api/driver/workbench?driver_id={driver_id}")
    workflow_event = request(
        "POST",
        "/api/driver/workflow-event",
        {
            "driver_id": driver_id,
            "assignment_id": assignment_id,
            "event_type": "vehicle_check_out",
            "latitude": 35.68,
            "longitude": 139.76,
            "location_text": "verify vehicle check",
            "note": "verify workflow event",
        },
    )
    roll_call_out_event = request(
        "POST",
        "/api/driver/workflow-event",
        {
            "driver_id": driver_id,
            "assignment_id": assignment_id,
            "event_type": "roll_call_out",
            "latitude": 35.68,
            "longitude": 139.76,
            "location_text": "verify roll call out",
            "note": "verify depart workflow state",
        },
    )
    workbench_after_roll_call_out = request("GET", f"/api/driver/workbench?driver_id={driver_id}")
    vehicle_status_after_roll_call_out = _vehicle_status(vehicle_id)
    workflow_events = request("GET", f"/api/driver/workflow-events?driver_id={driver_id}")["events"]
    expense_report = request(
        "POST",
        "/api/driver/expense",
        {
            "driver_id": driver_id,
            "assignment_id": assignment_id,
            "expense_kind": "advance",
            "category": "parking",
            "amount": 1200,
            "note": "verify driver expense",
            "submit_status": "submitted",
        },
    )
    collect_report = request(
        "POST",
        "/api/driver/expense",
        {
            "driver_id": driver_id,
            "assignment_id": assignment_id,
            "expense_kind": "collect",
            "category": "代收车费",
            "amount": 3000,
            "note": "verify collect expense",
            "submit_status": "in_hand",
        },
    )
    expense_reports = request("GET", f"/api/driver/expenses?driver_id={driver_id}")["expenses"]

    statuses = []
    vehicle_status_flow = {}
    for report_type in ["confirm_order", "depart_yard", "arrive_pickup", "start_service", "complete_order", "return_yard"]:
        report = request(
            "POST",
            "/api/driver/report",
            {
                "driver_id": driver_id,
                "assignment_id": assignment_id,
                "report_type": report_type,
                "latitude": 35.68,
                "longitude": 139.76,
                "location_text": "东京站附近",
                "note": f"{report_type} smoke",
            },
        )
        statuses.append(report.get("new_execution_status"))
        if report_type in {"depart_yard", "start_service", "return_yard"}:
            vehicle_status_flow[report_type] = _vehicle_status(vehicle_id)
    roll_call_in_event = request(
        "POST",
        "/api/driver/workflow-event",
        {
            "driver_id": driver_id,
            "assignment_id": assignment_id,
            "event_type": "roll_call_in",
            "latitude": 35.68,
            "longitude": 139.76,
            "location_text": "verify roll call in",
            "note": "verify return workflow state",
        },
    )
    duplicate_report = request(
        "POST",
        "/api/driver/report",
        {
            "driver_id": driver_id,
            "assignment_id": assignment_id,
            "report_type": "return_yard",
            "latitude": 35.68,
            "longitude": 139.76,
            "location_text": "duplicate smoke",
        },
    )
    manual_location = request(
        "POST",
        "/api/driver/location",
        {
            "driver_id": driver_id,
            "assignment_id": assignment_id,
            "latitude": 35.681,
            "longitude": 139.761,
            "location_text": "manual location smoke",
            "source": "verify_driver_api",
        },
    )
    evidence_upload = request(
        "POST",
        "/api/driver/evidence",
        {
            "driver_id": driver_id,
            "assignment_id": assignment_id,
            "evidence_type": "pickup",
            "image_base64": TEST_PNG_BASE64,
            "note": "verify pickup evidence",
        },
    )
    waypoint_evidence_upload = request(
        "POST",
        "/api/driver/evidence",
        {
            "driver_id": driver_id,
            "assignment_id": assignment_id,
            "evidence_type": "waypoint_photo",
            "image_base64": TEST_PNG_BASE64,
            "note": "verify waypoint evidence",
        },
    )
    dropoff_evidence_upload = request(
        "POST",
        "/api/driver/evidence",
        {
            "driver_id": driver_id,
            "assignment_id": assignment_id,
            "evidence_type": "dropoff_photo",
            "image_base64": TEST_PNG_BASE64,
            "note": "verify dropoff evidence",
        },
    )
    safety_incident = request(
        "POST",
        "/api/driver/incident",
        {
            "driver_id": driver_id,
            "assignment_id": assignment_id,
            "incident_kind": "sos",
            "latitude": 35.682,
            "longitude": 139.762,
            "location_text": "sos smoke location",
            "note": "verify sos incident",
        },
    )

    returned_detail = request("GET", f"/api/driver/assignments/{assignment_id}?driver_id={driver_id}")["assignment"]
    reports = request("GET", f"/api/driver/reports?driver_id={driver_id}")["reports"]
    evidence = request("GET", f"/api/driver/evidence?driver_id={driver_id}&assignment_id={assignment_id}")["evidence"]
    assignment_evidence_chain = request("GET", f"/api/assignments/{assignment_id}/evidence")["evidence_chain"]
    order_evidence_chain = request("GET", f"/api/orders/{order['id']}/evidence")["evidence_chain"]
    safety_alerts = request("GET", "/api/driver/safety-alerts")["alerts"]
    locations = request("GET", f"/api/driver/locations?driver_id={driver_id}")["locations"]
    latest_locations = request("GET", f"/api/fleet/latest-locations?driver_id={driver_id}")["locations"]
    latest_for_driver = next((item for item in latest_locations if item.get("driver_id") == driver_id), {})
    driver_dashboard = request("GET", f"/api/driver/dashboard?driver_id={driver_id}")
    workbench_after = request("GET", f"/api/driver/workbench?driver_id={driver_id}")
    driver_history = request("GET", f"/api/driver/history?driver_id={driver_id}")["history"]
    summary = request("GET", "/api/dashboard/summary")

    result = {
        "ping_ok": ping.get("ok") is True,
        "login_user": login.get("user", {}).get("username"),
        "assignment_id": assignment_id,
        "next_assignment_id": next_assignment_id,
        "driver_notifications_count": len(driver_notifications),
        "driver_new_order_notification": len(new_order_notifications) > 0,
        "driver_notification_read_success": notification_read.get("notification", {}).get("status") == "read",
        "driver_notification_read_status": next(
            (item.get("status") for item in driver_notifications_after_read if item.get("id") == first_notification_id),
            None,
        ),
        "own_assignment_visible": any(item["assignment_id"] == assignment_id for item in own_assignments),
        "next_assignment_visible": any(item["assignment_id"] == next_assignment_id for item in own_assignments),
        "public_driver_detail_visible": public_detail.get("assignment", {}).get("assignment_id") == assignment_id,
        "detail_execution_status_initial": detail.get("execution_status"),
        "other_driver_blocked": other_detail.get("_status") == 404,
        "workbench_initial_today_orders": workbench_initial.get("today_order_count"),
        "workbench_initial_has_next_step": bool(workbench_initial.get("next_step")),
        "workflow_event_success": workflow_event.get("success") is True,
        "roll_call_out_success": roll_call_out_event.get("success") is True,
        "workbench_after_roll_call_out_vehicle_status": workbench_after_roll_call_out.get("vehicle_status"),
        "vehicle_status_after_roll_call_out": vehicle_status_after_roll_call_out,
        "roll_call_in_success": roll_call_in_event.get("success") is True,
        "workflow_event_visible": any(item.get("assignment_id") == assignment_id for item in workflow_events),
        "expense_report_success": expense_report.get("success") is True,
        "collect_report_success": collect_report.get("success") is True,
        "expense_report_visible": any(item.get("assignment_id") == assignment_id for item in expense_reports),
        "collect_report_visible": any(item.get("expense_kind") == "collect" and item.get("category") == "代收车费" for item in expense_reports),
        "status_flow": statuses,
        "vehicle_status_flow": vehicle_status_flow,
        "vehicle_outbound_after_depart": vehicle_status_flow.get("depart_yard") == "outbound",
        "vehicle_in_service_after_start": vehicle_status_flow.get("start_service") == "in_service",
        "vehicle_returned_after_return": vehicle_status_flow.get("return_yard") == "returned",
        "duplicate_report_blocked": duplicate_report.get("success") is False,
        "manual_location_success": manual_location.get("success") is True,
        "evidence_upload_success": evidence_upload.get("success") is True,
        "waypoint_evidence_upload_success": waypoint_evidence_upload.get("success") is True,
        "dropoff_evidence_upload_success": dropoff_evidence_upload.get("success") is True,
        "evidence_upload_type": evidence_upload.get("evidence", {}).get("evidence_type"),
        "evidence_visible": any(item.get("assignment_id") == assignment_id for item in evidence),
        "assignment_evidence_timeline_visible": len(assignment_evidence_chain.get("timeline", [])) >= 1,
        "assignment_evidence_photo_count": assignment_evidence_chain.get("summary", {}).get("photo_count"),
        "assignment_evidence_expense_count": assignment_evidence_chain.get("summary", {}).get("expense_count"),
        "order_evidence_chain_visible": order_evidence_chain.get("assignment", {}).get("assignment_id") == assignment_id,
        "evidence_download_files_visible": len(assignment_evidence_chain.get("download_files", [])) >= 1,
        "sos_incident_success": safety_incident.get("success") is True,
        "sos_incident_type": safety_incident.get("incident", {}).get("incident_type"),
        "safety_alert_visible": any(item.get("assignment_id") == assignment_id for item in safety_alerts),
        "location_logs_written": any(item.get("assignment_id") == assignment_id for item in locations),
        "latest_location_visible": any(item.get("driver_id") == driver_id for item in latest_locations),
        "fleet_latest_has_vehicle_status": bool(latest_for_driver.get("vehicle_status")),
        "fleet_latest_has_execution_status": bool(latest_for_driver.get("execution_status")),
        "fleet_latest_has_order_status": bool(latest_for_driver.get("dispatch_status")),
        "fleet_latest_has_current_order": bool(latest_for_driver.get("oid")),
        "final_execution_status": returned_detail.get("execution_status"),
        "report_count_for_assignment": len([item for item in reports if item["assignment_id"] == assignment_id]),
        "driver_dashboard_count": driver_dashboard.get("active_assignment_count"),
        "driver_dashboard_today_orders": driver_dashboard.get("today_order_count"),
        "driver_dashboard_today_completed": driver_dashboard.get("today_completed_count"),
        "driver_dashboard_today_amount": driver_dashboard.get("today_estimated_amount"),
        "workbench_after_vehicle_status": workbench_after.get("vehicle_status"),
        "workbench_after_pending_expenses": workbench_after.get("today_pending_expenses"),
        "driver_history_visible": any(item.get("assignment_id") == assignment_id for item in driver_history),
        "dashboard_returned_orders": summary.get("today_returned_orders"),
        "dashboard_unreported_assignments": summary.get("unreported_assignments"),
        "dashboard_assigned_unconfirmed_orders": summary.get("assigned_unconfirmed_orders"),
        "dashboard_confirmed_driver_count": summary.get("confirmed_driver_count"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _format_time(total_minutes: int) -> str:
    hour = (total_minutes // 60) % 24
    minute = total_minutes % 60
    return f"{hour:02d}:{minute:02d}"


def _vehicle_status(vehicle_id: int) -> str | None:
    with get_connection() as conn:
        row = conn.execute("SELECT status FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
    return row["status"] if row else None


if __name__ == "__main__":
    main()
