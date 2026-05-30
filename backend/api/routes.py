import json
import logging
import mimetypes
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from backend.services.auth_service import (
    authenticate,
    authenticate_phone,
    change_user_password,
    get_user_by_token,
    register_bound_account,
    resolve_wechat_login_code,
    reset_user_password_to_phone_tail,
    unbind_user_wechat,
)
from backend.services.agency_portal_service import (
    agency_portal_login,
    create_agency_order,
    list_agency_orders,
    list_public_agencies,
)
from backend.services.agency_service import create_agency, delete_agency, list_agencies, update_agency
from backend.services.account_service import (
    create_account,
    disable_account,
    enable_account,
    get_account_overview,
    reset_account_password,
    unbind_account_wechat,
    update_account,
)
from backend.services.analytics_service import get_analytics_summary
from backend.services.attendance_service import export_driver_attendance_csv, get_driver_attendance_daily, get_driver_attendance_ledger
from backend.services.audit_service import (
    get_entity_history,
    list_anomaly_scans,
    list_audit_logs,
    record_audit,
    scan_data_anomalies,
)
from backend.services.billing_service import (
    get_billing_overview,
    get_feature_flags,
    get_subscription,
    get_usage,
    is_feature_enabled,
    list_plans,
    update_subscription,
)
from backend.services.calendar_service import get_dispatch_calendar, get_dispatch_detail
from backend.services.dashboard_service import get_summary
from backend.services.dispatch_service import (
    assign_orders,
    cancel_assignment,
    list_assignments,
    list_available_drivers,
    list_available_vehicles,
    list_unassigned_orders,
    reassign_orders,
    route_suggestion,
)
from backend.services.dispatch_brain_service import recommend_dispatch
from backend.services.dispatch_mobile_audit_service import list_dispatch_mobile_audit_logs, record_dispatch_mobile_audit
from backend.services.dispatcher_mobile_service import (
    get_dispatcher_context,
    get_dispatcher_dashboard,
    get_dispatcher_notifications,
    get_shared_runtime_state,
    list_dispatcher_unassigned_orders,
    login_dispatcher,
    login_dispatcher_by_wechat,
    mark_order_dispatcher_context,
    parse_dispatcher_text,
    update_dispatcher_draft,
)
from backend.services.driver_service import (
    get_driver_assignment,
    get_assignment_evidence_chain,
    get_driver_dashboard,
    get_driver_profile,
    get_driver_workbench,
    get_order_evidence_chain,
    list_driver_evidence,
    list_driver_assignments,
    list_driver_expenses,
    list_driver_history,
    list_driver_reports,
    list_driver_safety_alerts,
    list_driver_workflow_events,
    submit_driver_expense,
    submit_driver_incident,
    submit_driver_location,
    submit_driver_report,
    submit_driver_workflow_event,
    update_driver_profile,
    upload_driver_evidence,
    upload_driver_profile_document,
)
from backend.services.finance_service import (
    export_finance_csv,
    get_driver_income_summary,
    get_driver_settlement_stats,
    get_finance_driver_expense,
    get_finance_ledger,
    get_finance_summary,
    list_finance_driver_expenses,
    update_finance_driver_expense,
    update_settlement,
)
from backend.services.incident_service import close_incident, create_incident, get_incident_summary, list_incidents
from backend.services.location_service import get_fleet_location_summary, get_latest_locations, list_location_logs
from backend.services.order_service import create_order, get_order, list_orders, soft_delete_order, update_order
from backend.services.operation_log_service import log_operation
from backend.services.notification_service import (
    create_notification,
    get_notification_summary,
    list_driver_notifications,
    list_notifications,
    mark_all_notifications_read,
    mark_driver_notification_read,
    mark_notification_read,
)
from backend.services.org_service import (
    create_department,
    create_team,
    disable_member,
    get_org_overview,
    get_role_permissions,
    invite_member,
    list_departments,
    list_members,
    list_teams,
    update_member,
)
from backend.services.operations_copilot_service import get_copilot_summary
from backend.services.parser_service import (
    confirm_draft,
    discard_draft,
    get_draft,
    list_drafts,
    parse_excel_to_drafts,
    parse_batch_text_to_drafts,
    parse_text_to_draft,
    parse_voice_to_draft,
    update_draft,
)
from backend.services.resource_service import (
    create_driver,
    create_vehicle,
    create_vehicle_inspection_record,
    delete_driver,
    delete_vehicle,
    delete_vehicle_inspection_record,
    get_resource_reminders,
    list_drivers,
    list_vehicles,
    update_driver,
    update_vehicle,
    update_vehicle_inspection_record,
)
from backend.services.settings_service import get_reminder_settings, update_reminder_settings
from backend.services.system_maintenance_service import (
    backup_database,
    get_system_status,
    run_system_health,
    schedule_api_restart,
    tail_backend_log,
)
from backend.services.tenant_context import set_current_tenant_id
from backend.services.workflow_service import create_rule, list_rules, list_runs, run_workflows, update_rule

ROOT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIST_DIR = ROOT_DIR / "frontend" / "dist"
UPLOAD_DIR = ROOT_DIR / "runtime" / "uploads"


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "WXDispatchAPI/0.6"

    def handle_one_request(self) -> None:
        try:
            super().handle_one_request()
        except BrokenPipeError:
            logging.warning("client disconnected while handling request")
        except Exception as exc:  # noqa: BLE001 - production runtime must log uncaught API failures.
            logging.exception("unhandled_api_error path=%s error=%s", getattr(self, "path", "-"), exc)
            try:
                self.send_json(
                    {"error": "internal_server_error", "message": "Request failed. Check backend logs."},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            except Exception:
                pass

    def log_message(self, format: str, *args) -> None:
        logging.info("http %s - %s", self.address_string(), format % args)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT.value)
        self.end_headers()

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Driver-Id, X-Agency-Token")
        super().end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        params = self.query_params(parsed.query)
        if path == "/driver-google-map":
            self.send_driver_google_map_page(params)
            return
        if path == "/api/ping":
            self.send_json({"ok": True, "message": "pong"})
            return
        if path == "/api/agency-portal/agencies":
            self.send_json({"agencies": list_public_agencies()})
            return
        if path == "/api/agency-portal/orders":
            self.safe_agency(lambda: {"orders": list_agency_orders(self.agency_token())})
            return
        if path.startswith("/api/") and path != "/api/auth/me" and not path.startswith("/api/driver/") and not path.startswith("/api/dispatch-mobile/"):
            user = self.require_api_user()
            if not user:
                return
        if path == "/api/dispatch-mobile/context":
            self.send_json(get_dispatcher_context(params))
            return
        if path == "/api/dispatch-mobile/dashboard":
            self.send_json(get_dispatcher_dashboard(params))
            return
        if path == "/api/dispatch-mobile/shared-state":
            self.send_json(get_shared_runtime_state(params))
            return
        if path == "/api/dispatch-mobile/unassigned-orders":
            self.send_json({"orders": list_dispatcher_unassigned_orders(params)})
            return
        if path == "/api/dispatch-mobile/drafts":
            self.send_json({"drafts": list_drafts()})
            return
        if path == "/api/dispatch-mobile/drivers":
            if not self.require_role({"admin", "dispatcher", "operations_manager"}):
                return
            self.send_json({"drivers": list_available_drivers()})
            return
        if path == "/api/dispatch-mobile/vehicles":
            self.send_json({"vehicles": list_available_vehicles()})
            return
        if path == "/api/dispatch-mobile/assignments":
            if not self.require_role({"admin", "dispatcher", "operations_manager"}):
                return
            self.send_json({"assignments": list_assignments(params.get("status", "active"))})
            return
        if path == "/api/dispatch-mobile/fleet/latest-locations":
            self.send_json({
                "locations": get_latest_locations(
                    params.get("driver_id"),
                    int(params.get("limit") or 50),
                    params.get("online_status"),
                )
            })
            return
        if path == "/api/dispatch-mobile/finance/summary":
            if not self.require_role({"admin"}):
                return
            self.send_json(get_finance_summary(params))
            return
        if path == "/api/dispatch-mobile/finance/ledger":
            if not self.require_role({"admin"}):
                return
            self.send_json(get_finance_ledger(params))
            return
        if path == "/api/dispatch-mobile/notifications":
            self.send_json(get_dispatcher_notifications(params))
            return
        if path == "/api/dispatch-mobile/audit-logs":
            self.send_json({"logs": list_dispatch_mobile_audit_logs(params)})
            return
        if path == "/api/auth/me":
            user = self.require_api_user()
            if not user:
                return
            self.send_json({"user": user} if user else {"error": "unauthorized"}, HTTPStatus.OK if user else HTTPStatus.UNAUTHORIZED)
            return
        if path == "/api/dashboard/summary":
            self.send_json(get_summary())
            return
        if path == "/api/analytics/summary":
            if not self.require_role({"admin"}):
                return
            self.send_json(get_analytics_summary(params))
            return
        if path == "/api/audit/logs":
            self.send_json({"logs": list_audit_logs(params)})
            return
        if path == "/api/audit/history":
            entity_type = params.get("entity_type", "")
            entity_id = params.get("entity_id", "")
            if not entity_type or not entity_id:
                self.send_json({"error": "missing_entity_type_or_id"}, HTTPStatus.BAD_REQUEST)
                return
            self.send_json({"history": get_entity_history(entity_type, entity_id, int(params.get("limit") or 100))})
            return
        if path == "/api/audit/anomalies":
            self.send_json(scan_data_anomalies())
            return
        if path == "/api/audit/scans":
            self.send_json({"scans": list_anomaly_scans(int(params.get("limit") or 20))})
            return
        if path == "/api/workflows/rules":
            self.send_json({"rules": list_rules()})
            return
        if path == "/api/workflows/runs":
            self.send_json({"runs": list_runs(int(params.get("limit") or 50))})
            return
        if path == "/api/copilot/summary":
            self.send_json(get_copilot_summary(params))
            return
        if path == "/api/attendance/daily":
            self.send_json(get_driver_attendance_daily(params.get("date")))
            return
        if path == "/api/attendance/ledger":
            self.send_json(get_driver_attendance_ledger(params))
            return
        if path == "/api/attendance/export":
            self.send_csv(export_driver_attendance_csv(params), "attendance_ledger.csv")
            return
        if path == "/api/notifications":
            user = self.require_api_user()
            if not user:
                return
            self.send_json({"notifications": self.visible_notifications(user, params)})
            return
        if path == "/api/notifications/summary":
            user = self.require_api_user()
            if not user:
                return
            visible = self.visible_notifications(user, {**params, "limit": 500})
            self.send_json({
                "total": len(visible),
                "unread": len([item for item in visible if item.get("status") != "read"]),
                "urgent": len([item for item in visible if item.get("status") != "read" and item.get("priority") in {"high", "critical"}]),
                "latest": visible[:8],
            })
            return
        if path == "/api/incidents":
            self.send_json({"incidents": list_incidents(params)})
            return
        if path == "/api/incidents/summary":
            self.send_json(get_incident_summary())
            return
        if path == "/api/billing/plans":
            if not self.require_role({"admin"}):
                return
            self.send_json({"plans": list_plans()})
            return
        if path == "/api/billing/subscription":
            if not self.require_role({"admin"}):
                return
            self.send_json({"subscription": get_subscription()})
            return
        if path == "/api/billing/usage":
            if not self.require_role({"admin"}):
                return
            self.send_json(get_usage())
            return
        if path == "/api/billing/features":
            if not self.require_role({"admin"}):
                return
            self.send_json({"feature_flags": get_feature_flags()})
            return
        if path == "/api/billing/overview":
            if not self.require_role({"admin"}):
                return
            self.send_json(get_billing_overview())
            return
        if path == "/api/org/overview":
            self.send_json(get_org_overview())
            return
        if path == "/api/org/departments":
            self.send_json({"departments": list_departments()})
            return
        if path == "/api/org/teams":
            self.send_json({"teams": list_teams()})
            return
        if path == "/api/org/members":
            self.send_json({"members": list_members()})
            return
        if path == "/api/org/roles":
            self.send_json({"role_permissions": get_role_permissions()})
            return
        if path == "/api/accounts/overview":
            if not self.require_role({"admin"}):
                return
            self.send_json(get_account_overview())
            return
        if path == "/api/system/status":
            if not self.require_role({"admin"}):
                return
            self.send_json(get_system_status())
            return
        if path == "/api/system/health":
            if not self.require_role({"admin"}):
                return
            self.send_json(run_system_health())
            return
        if path == "/api/system/logs":
            if not self.require_role({"admin"}):
                return
            self.send_json(tail_backend_log(int(params.get("lines") or 120)))
            return
        if path == "/api/agencies":
            self.send_json({"agencies": list_agencies(params)})
            return
        if path == "/api/finance/summary":
            if not self.require_role({"admin"}):
                return
            if not is_feature_enabled("finance"):
                self.send_json({"error": "feature_not_enabled", "feature": "finance"}, HTTPStatus.FORBIDDEN)
                return
            self.send_json(get_finance_summary(params))
            return
        if path == "/api/finance/ledger":
            if not self.require_role({"admin"}):
                return
            if not is_feature_enabled("finance"):
                self.send_json({"error": "feature_not_enabled", "feature": "finance"}, HTTPStatus.FORBIDDEN)
                return
            self.send_json(get_finance_ledger(params))
            return
        if path == "/api/finance/driver-stats":
            if not self.require_role({"admin"}):
                return
            if not is_feature_enabled("finance"):
                self.send_json({"error": "feature_not_enabled", "feature": "finance"}, HTTPStatus.FORBIDDEN)
                return
            self.send_json(get_driver_settlement_stats(params))
            return
        if path == "/api/finance/driver-expenses":
            if not self.require_role({"admin"}):
                return
            if not is_feature_enabled("finance"):
                self.send_json({"error": "feature_not_enabled", "feature": "finance"}, HTTPStatus.FORBIDDEN)
                return
            self.send_json(list_finance_driver_expenses(params))
            return
        if path == "/api/finance/export":
            if not self.require_role({"admin"}):
                return
            if not is_feature_enabled("finance"):
                self.send_json({"error": "feature_not_enabled", "feature": "finance"}, HTTPStatus.FORBIDDEN)
                return
            self.send_csv(export_finance_csv(params), "finance_export.csv")
            return
        if path == "/api/resources/drivers":
            self.send_json({"drivers": list_drivers(params.get("status"))})
            return
        if path == "/api/resources/vehicles":
            self.send_json({"vehicles": list_vehicles(params.get("status"))})
            return
        if path == "/api/resources/reminders":
            self.send_json(get_resource_reminders())
            return
        if path == "/api/settings/reminders":
            self.send_json({"settings": get_reminder_settings()})
            return
        if path == "/api/orders":
            self.send_json({"orders": list_orders(params)})
            return
        if path == "/api/calendar/dispatch":
            self.send_json(get_dispatch_calendar(params))
            return
        detail_id = self.match_calendar_detail_path(path)
        if detail_id:
            detail = get_dispatch_detail(detail_id)
            self.send_json({"ok": True, "detail": detail} if detail else {"ok": False, "error": "assignment_not_found"}, HTTPStatus.OK if detail else HTTPStatus.NOT_FOUND)
            return
        if path == "/api/dispatch/unassigned-orders":
            if not self.require_role({"admin", "dispatcher"}):
                return
            self.send_json({"orders": list_unassigned_orders()})
            return
        if path == "/api/dispatch/drivers":
            self.send_json({"drivers": list_available_drivers()})
            return
        if path == "/api/dispatch/vehicles":
            self.send_json({"vehicles": list_available_vehicles()})
            return
        if path == "/api/dispatch/assignments":
            self.send_json({"assignments": list_assignments(params.get("status", "active"))})
            return
        if path == "/api/dispatch/route-suggestion":
            self.send_json(route_suggestion(self.parse_ids(params.get("order_ids", ""))))
            return
        if path == "/api/parser/drafts":
            self.send_json({"drafts": list_drafts(params.get("parse_status"))})
            return
        if path == "/api/driver/assignments":
            self.send_json({"assignments": list_driver_assignments(self.driver_id(params))})
            return
        driver_assignment_id = self.match_driver_assignment_path(path)
        if driver_assignment_id:
            assignment = get_driver_assignment(self.driver_id(params), driver_assignment_id)
            self.send_json({"assignment": assignment} if assignment else {"error": "assignment_not_found_for_driver"}, HTTPStatus.OK if assignment else HTTPStatus.NOT_FOUND)
            return
        if path == "/api/driver/reports":
            self.send_json({"reports": list_driver_reports(self.driver_id(params))})
            return
        if path == "/api/driver/locations":
            self.send_json({"locations": list_location_logs(self.driver_id(params), int(params.get("limit") or 100))})
            return
        if path == "/api/fleet/latest-locations":
            self.send_json({
                "locations": get_latest_locations(
                    params.get("driver_id"),
                    int(params.get("limit") or 50),
                    params.get("online_status"),
                    params.get("vehicle_status"),
                )
            })
            return
        if path == "/api/fleet/location-summary":
            self.send_json(get_fleet_location_summary())
            return
        if path == "/api/driver/dashboard":
            self.send_json(get_driver_dashboard(self.driver_id(params)))
            return
        if path == "/api/driver/profile":
            self.send_json(get_driver_profile(self.driver_id(params)))
            return
        if path == "/api/driver/workbench":
            self.send_json(get_driver_workbench(self.driver_id(params)))
            return
        if path == "/api/driver/workflow-events":
            self.send_json({"events": list_driver_workflow_events(self.driver_id(params), params.get("date"))})
            return
        if path == "/api/driver/expenses":
            self.send_json({"expenses": list_driver_expenses(self.driver_id(params), params)})
            return
        if path == "/api/driver/history":
            self.send_json({"history": list_driver_history(self.driver_id(params), params)})
            return
        if path == "/api/driver/income":
            self.send_json(get_driver_income_summary(self.driver_id(params), params))
            return
        if path == "/api/driver/notifications":
            self.send_json({"notifications": list_driver_notifications(self.driver_id(params), params)})
            return
        if path == "/api/driver/safety-alerts":
            self.send_json({"alerts": list_driver_safety_alerts()})
            return
        if path == "/api/driver/evidence":
            self.send_json({"evidence": list_driver_evidence(self.driver_id(params), params.get("assignment_id"))})
            return
        assignment_evidence_id = self.match_assignment_evidence_path(path)
        if assignment_evidence_id:
            user = self.require_api_user()
            if not user:
                return
            evidence_chain = get_assignment_evidence_chain(assignment_evidence_id)
            evidence_chain = self.sanitize_evidence_chain(evidence_chain, user)
            self.send_json({"evidence_chain": evidence_chain} if evidence_chain else {"error": "assignment_evidence_not_found"}, HTTPStatus.OK if evidence_chain else HTTPStatus.NOT_FOUND)
            return
        order_evidence_id = self.match_order_evidence_path(path)
        if order_evidence_id:
            user = self.require_api_user()
            if not user:
                return
            evidence_chain = get_order_evidence_chain(order_evidence_id)
            evidence_chain = self.sanitize_evidence_chain(evidence_chain, user)
            self.send_json({"evidence_chain": evidence_chain} if evidence_chain else {"error": "order_evidence_not_found"}, HTTPStatus.OK if evidence_chain else HTTPStatus.NOT_FOUND)
            return
        draft_id = self.match_parser_draft_path(path)
        if draft_id:
            draft = get_draft(draft_id)
            self.send_json({"draft": draft} if draft else {"error": "draft_not_found"}, HTTPStatus.OK if draft else HTTPStatus.NOT_FOUND)
            return
        order_id = self.match_order_path(path)
        if order_id:
            order = get_order(order_id)
            self.send_json({"order": order} if order else {"error": "order_not_found"}, HTTPStatus.OK if order else HTTPStatus.NOT_FOUND)
            return
        if self.serve_upload_asset(path) or self.serve_frontend_asset(path):
            return
        self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        payload = self.read_json()
        if path == "/api/agency-portal/login":
            result = agency_portal_login(payload)
            self.send_json(result if result else {"error": "invalid_agency_credentials"}, HTTPStatus.OK if result else HTTPStatus.UNAUTHORIZED)
            return
        if path == "/api/agency-portal/orders":
            self.safe_agency(lambda: {"order": create_agency_order(self.agency_token(), payload)}, HTTPStatus.CREATED)
            return
        if path == "/api/dispatch-mobile/login":
            if payload.get("wx_code") and not payload.get("wx_openid"):
                try:
                    payload.update(resolve_wechat_login_code(payload.get("wx_code")))
                except ValueError as exc:
                    if str(exc) == "wechat_code_exchange_unavailable":
                        payload.pop("wx_code", None)
                        payload["client_type"] = "web"
                    else:
                        self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                        return
            result = login_dispatcher(payload)
            ok = bool(result and not result.get("error"))
            log_operation("DISPATCHER_MOBILE_LOGIN_OK" if ok else "DISPATCHER_MOBILE_LOGIN_FAIL", path, {"username": payload.get("username", ""), "phone": payload.get("phone", ""), "error": result.get("error") if result else "invalid_dispatcher_credentials"}, payload.get("username", "") or payload.get("phone", ""))
            self.send_json(result if result else {"error": "invalid_dispatcher_credentials"}, HTTPStatus.OK if ok else HTTPStatus.UNAUTHORIZED)
            return
        if path == "/api/dispatch-mobile/wechat-login":
            if payload.get("wx_code") and not payload.get("wx_openid"):
                try:
                    payload.update(resolve_wechat_login_code(payload.get("wx_code")))
                except ValueError as exc:
                    self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                    return
            result = login_dispatcher_by_wechat(payload)
            ok = bool(result and not result.get("error"))
            log_operation(
                "DISPATCHER_MOBILE_WECHAT_LOGIN_OK" if ok else "DISPATCHER_MOBILE_WECHAT_LOGIN_FAIL",
                path,
                {"error": result.get("error") if result else "wechat_not_bound"},
                "wechat",
            )
            self.send_json(result if result else {"error": "wechat_not_bound"}, HTTPStatus.OK if ok else HTTPStatus.UNAUTHORIZED)
            return
        public_auth_paths = {"/api/auth/login", "/api/auth/login-phone", "/api/auth/register"}
        if path.startswith("/api/") and path not in public_auth_paths and not path.startswith("/api/driver/") and not path.startswith("/api/dispatch-mobile/"):
            user = self.require_api_user()
            if not user:
                return
        if path not in public_auth_paths:
            log_operation("POST", path, payload, self.actor_label())
        if path == "/api/auth/login":
            result = authenticate(payload.get("username", ""), payload.get("password", ""))
            log_operation("LOGIN_OK" if result else "LOGIN_FAIL", path, {"username": payload.get("username", "")}, payload.get("username", ""))
            self.send_json(result if result else {"error": "invalid_credentials"}, HTTPStatus.OK if result else HTTPStatus.UNAUTHORIZED)
            return
        if path == "/api/auth/login-phone":
            phone_login_value = payload.get("phone") or payload.get("username") or payload.get("account") or ""
            if payload.get("wx_code") and not payload.get("wx_openid"):
                try:
                    payload.update(resolve_wechat_login_code(payload.get("wx_code")))
                except ValueError as exc:
                    if str(exc) == "wechat_code_exchange_unavailable":
                        payload.pop("wx_code", None)
                        payload["client_type"] = "web"
                    else:
                        self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                        return
            result = authenticate_phone(
                phone_login_value,
                payload.get("password", ""),
                payload.get("wx_openid"),
                payload.get("wx_unionid"),
                payload.get("client_type", "web"),
            )
            ok = bool(result and not result.get("error"))
            log_operation(
                "PHONE_LOGIN_OK" if ok else "PHONE_LOGIN_FAIL",
                path,
                {"phone": phone_login_value, "error": result.get("error") if result else "invalid_credentials"},
                phone_login_value,
            )
            self.send_json(result if result else {"error": "invalid_credentials"}, HTTPStatus.OK if ok else HTTPStatus.UNAUTHORIZED)
            return
        if path == "/api/auth/register":
            try:
                result = register_bound_account(payload)
            except ValueError as exc:
                log_operation("REGISTER_BIND_FAIL", path, {"phone": payload.get("phone", ""), "error": str(exc)}, payload.get("phone", ""))
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            log_operation("REGISTER_BIND_OK", path, {"phone": payload.get("phone", ""), "role": payload.get("role")}, payload.get("phone", ""))
            self.send_json(result, HTTPStatus.CREATED)
            return
        if path == "/api/auth/admin/unbind-wechat":
            if not self.require_role({"admin"}):
                return
            user = unbind_user_wechat(payload.get("user_id"), self.actor_label())
            self.send_json({"user": user} if user else {"error": "user_not_found"}, HTTPStatus.OK if user else HTTPStatus.NOT_FOUND)
            return
        if path == "/api/auth/admin/reset-password":
            if not self.require_role({"admin"}):
                return
            try:
                user = reset_user_password_to_phone_tail(payload.get("user_id"), self.actor_label())
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self.send_json({"user": user} if user else {"error": "user_not_found"}, HTTPStatus.OK if user else HTTPStatus.NOT_FOUND)
            return
        if path == "/api/auth/change-password":
            user = self.require_api_user()
            if not user:
                return
            try:
                changed = change_user_password(user.get("id"), payload.get("old_password", ""), payload.get("new_password", ""), self.actor_label())
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self.send_json({"user": changed} if changed else {"error": "user_not_found"}, HTTPStatus.OK if changed else HTTPStatus.NOT_FOUND)
            return
        if path == "/api/accounts":
            if not self.require_role({"admin"}):
                return
            self.safe_create(lambda: {"account": create_account(payload, self.actor_label())}, HTTPStatus.CREATED)
            return
        if path == "/api/system/backup":
            if not self.require_role({"admin"}):
                return
            try:
                self.send_json(backup_database(self.actor_label()), HTTPStatus.CREATED)
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if path == "/api/system/restart-api":
            if not self.require_role({"admin"}):
                return
            try:
                self.send_json(schedule_api_restart(), HTTPStatus.ACCEPTED)
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        account_disable_id = self._match_action_path(path, "/api/accounts/", "/disable")
        if account_disable_id:
            if not self.require_role({"admin"}):
                return
            self.safe_update(lambda: disable_account(account_disable_id, self.actor_label()), "account", "account_not_found")
            return
        account_enable_id = self._match_action_path(path, "/api/accounts/", "/enable")
        if account_enable_id:
            if not self.require_role({"admin"}):
                return
            self.safe_update(lambda: enable_account(account_enable_id, self.actor_label()), "account", "account_not_found")
            return
        account_reset_id = self._match_action_path(path, "/api/accounts/", "/reset-password")
        if account_reset_id:
            if not self.require_role({"admin"}):
                return
            self.safe_update(lambda: reset_account_password(account_reset_id, self.actor_label()), "account", "account_not_found")
            return
        account_unbind_id = self._match_action_path(path, "/api/accounts/", "/unbind-wechat")
        if account_unbind_id:
            if not self.require_role({"admin"}):
                return
            self.safe_update(lambda: unbind_account_wechat(account_unbind_id, self.actor_label()), "account", "account_not_found")
            return
        if path == "/api/orders":
            self.create_order_with_audit(payload, path)
            return
        if path == "/api/incidents":
            self.safe_create(lambda: {"incident": create_incident(payload)}, HTTPStatus.CREATED)
            return
        if path == "/api/billing/subscription":
            if not self.require_role({"admin"}):
                return
            self.safe_create(lambda: {"subscription": update_subscription(payload)})
            return
        if path == "/api/org/departments":
            if not self.require_role({"admin"}):
                return
            self.safe_create(lambda: {"department": create_department(payload)}, HTTPStatus.CREATED)
            return
        if path == "/api/org/teams":
            if not self.require_role({"admin"}):
                return
            self.safe_create(lambda: {"team": create_team(payload)}, HTTPStatus.CREATED)
            return
        if path == "/api/org/members/invite":
            if not self.require_role({"admin"}):
                return
            self.safe_create(lambda: {"member": invite_member(payload)}, HTTPStatus.CREATED)
            return
        if path == "/api/agencies":
            self.safe_create(lambda: {"agency": create_agency(payload)}, HTTPStatus.CREATED)
            return
        if path == "/api/notifications":
            self.safe_create(lambda: {"notification": create_notification(payload)}, HTTPStatus.CREATED)
            return
        if path == "/api/workflows/rules":
            self.safe_create(lambda: {"rule": create_rule(payload)}, HTTPStatus.CREATED)
            return
        if path == "/api/workflows/run":
            self.safe_create(lambda: run_workflows(payload))
            return
        if path == "/api/notifications/read-all":
            user = self.require_api_user()
            if not user:
                return
            visible = self.visible_notifications(user, {"status": "unread", "limit": 500})
            updated = 0
            for item in visible:
                if mark_notification_read(item.get("id")):
                    updated += 1
            self.send_json({"updated": updated})
            return
        notification_read_id = self.match_notification_read_path(path)
        if notification_read_id:
            user = self.require_api_user()
            if not user:
                return
            if not any(str(item.get("id")) == str(notification_read_id) for item in self.visible_notifications(user, {"limit": 500})):
                self.send_json({"error": "notification_not_found"}, HTTPStatus.NOT_FOUND)
                return
            self.safe_update(lambda: mark_notification_read(notification_read_id), "notification", "notification_not_found")
            return
        org_disable_id = self.match_org_disable_path(path)
        if org_disable_id:
            if not self.require_role({"admin"}):
                return
            self.safe_update(lambda: disable_member(org_disable_id), "member", "member_not_found")
            return
        incident_close_id = self.match_incident_close_path(path)
        if incident_close_id:
            self.safe_update(lambda: close_incident(incident_close_id, payload), "incident", "incident_not_found")
            return
        if path == "/api/resources/drivers":
            self.safe_create(lambda: {"driver": create_driver(payload)}, HTTPStatus.CREATED)
            return
        if path == "/api/resources/vehicles":
            self.safe_create(lambda: {"vehicle": create_vehicle(payload)}, HTTPStatus.CREATED)
            return
        vehicle_records_id = self._match_action_path(path, "/api/resources/vehicles/", "/inspection-records")
        if vehicle_records_id:
            try:
                record = create_vehicle_inspection_record(vehicle_records_id, payload)
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self.send_json({"record": record} if record else {"error": "vehicle_not_found"}, HTTPStatus.CREATED if record else HTTPStatus.NOT_FOUND)
            return
        if path == "/api/settings/reminders":
            self.safe_create(lambda: {"settings": update_reminder_settings(payload)})
            return
        if path == "/api/dispatch/assign":
            if not self.require_role({"admin", "dispatcher"}):
                return
            self.dispatch_assign_with_audit(payload, path)
            return
        if path == "/api/dispatch/recommend":
            if not self.require_role({"admin", "dispatcher"}):
                return
            self.safe_create(lambda: recommend_dispatch(payload.get("order_ids", [])))
            return
        if path == "/api/dispatch/cancel":
            if not self.require_role({"admin", "dispatcher"}):
                return
            self.dispatch_cancel_with_audit(payload, path)
            return
        if path == "/api/dispatch/reassign":
            if not self.require_role({"admin", "dispatcher"}):
                return
            self.dispatch_reassign_with_audit(payload, path)
            return
        if path == "/api/driver/profile":
            self.send_json(update_driver_profile(payload.get("driver_id"), payload))
            return
        if path == "/api/driver/profile-document":
            self.send_json(upload_driver_profile_document(payload), HTTPStatus.CREATED)
            return
        if path == "/api/parser/text":
            if payload.get("batch"):
                drafts = parse_batch_text_to_drafts(payload.get("text", ""), "text")
                self.send_json({"drafts": drafts, "count": len(drafts)}, HTTPStatus.CREATED)
                return
            draft = parse_text_to_draft(payload.get("text", ""), "text")
            self.send_json({"draft": draft, "parse_result": draft.get("parse_result"), "parse_status": draft["parse_status"]}, HTTPStatus.CREATED)
            return
        if path == "/api/dispatch-mobile/parser/text":
            self.send_json(parse_dispatcher_text(payload), HTTPStatus.CREATED)
            return
        if path == "/api/dispatch-mobile/order-context":
            order = mark_order_dispatcher_context(payload.get("order_id"), payload, bool(payload.get("update_only")))
            self.send_json({"ok": bool(order), "order": order} if order else {"ok": False, "error": "order_not_found"}, HTTPStatus.OK if order else HTTPStatus.NOT_FOUND)
            return
        if path == "/api/dispatch-mobile/dispatch/assign":
            if not self.require_role({"admin", "dispatcher"}):
                return
            self.dispatch_assign_with_audit(payload, path)
            return
        if path == "/api/parser/excel":
            drafts = parse_excel_to_drafts(payload)
            self.send_json({"drafts": drafts, "count": len(drafts)}, HTTPStatus.CREATED)
            return
        if path == "/api/parser/voice":
            draft = parse_voice_to_draft(payload)
            self.send_json({"draft": draft, "parse_result": draft.get("parse_result"), "parse_status": draft["parse_status"]}, HTTPStatus.CREATED)
            return
        mobile_draft_id = self.match_dispatch_mobile_draft_path(path)
        if mobile_draft_id:
            draft = update_dispatcher_draft(mobile_draft_id, payload)
            self.send_json({"draft": draft} if draft else {"error": "draft_not_found"}, HTTPStatus.OK if draft else HTTPStatus.NOT_FOUND)
            return
        mobile_confirm_id = self.match_dispatch_mobile_confirm_path(path)
        if mobile_confirm_id:
            result = confirm_draft(mobile_confirm_id)
            if result and result.get("order_id"):
                result["order"] = mark_order_dispatcher_context(result["order_id"], payload) or result.get("order")
                record_dispatch_mobile_audit(
                    "mobile_confirm_order",
                    payload,
                    entity_type="order",
                    entity_id=result.get("order_id"),
                    after=result,
                    summary=f"Mobile confirmed draft {mobile_confirm_id} to order {result.get('order_id')}",
                    source_path=path,
                )
            self.send_json(result if result else {"error": "draft_not_found"}, HTTPStatus.OK if result else HTTPStatus.NOT_FOUND)
            return
        mobile_order_update_id = self.match_dispatch_mobile_order_update_path(path)
        if mobile_order_update_id:
            before = get_order(mobile_order_update_id)
            order = update_order(mobile_order_update_id, payload)
            if order:
                mark_order_dispatcher_context(order["id"], payload, True)
                record_dispatch_mobile_audit(
                    "mobile_order_update",
                    payload,
                    entity_type="order",
                    entity_id=order.get("id"),
                    before=before,
                    after=order,
                    summary=f"Mobile updated order {order.get('oid') or order.get('id')}",
                    source_path=path,
                )
            self.send_json({"order": order} if order else {"error": "order_not_found"}, HTTPStatus.OK if order else HTTPStatus.NOT_FOUND)
            return
        if path == "/api/driver/report":
            result = submit_driver_report(payload)
            record_audit(
                "driver_report",
                "assignment",
                payload.get("assignment_id"),
                after=result,
                actor=self.actor_label(),
                source_path=path,
                summary=f"Driver report {payload.get('report_type')} for assignment {payload.get('assignment_id')}",
            )
            self.send_json(result)
            return
        if path == "/api/audit/scan":
            self.send_json(scan_data_anomalies())
            return
        if path == "/api/driver/location":
            self.send_json(submit_driver_location(payload))
            return
        if path == "/api/driver/workflow-event":
            self.send_json(submit_driver_workflow_event(payload), HTTPStatus.CREATED)
            return
        if path == "/api/driver/expense":
            self.send_json(submit_driver_expense(payload), HTTPStatus.CREATED)
            return
        if path == "/api/driver/incident":
            self.send_json(submit_driver_incident(payload), HTTPStatus.CREATED)
            return
        if path == "/api/driver/evidence":
            self.send_json(upload_driver_evidence(payload), HTTPStatus.CREATED)
            return
        driver_notification_read_id = self.match_driver_notification_read_path(path)
        if driver_notification_read_id:
            notification = mark_driver_notification_read(payload.get("driver_id") or self.driver_id({}), driver_notification_read_id)
            self.send_json({"notification": notification} if notification else {"error": "notification_not_found"}, HTTPStatus.OK if notification else HTTPStatus.NOT_FOUND)
            return
        confirm_id = self.match_parser_confirm_path(path)
        if confirm_id:
            result = confirm_draft(confirm_id)
            if result and result.get("order_id") and (payload.get("dispatcher_id") or payload.get("dispatcher_code") or payload.get("dispatcher_name")):
                result["order"] = mark_order_dispatcher_context(result["order_id"], payload) or result.get("order")
                record_dispatch_mobile_audit(
                    "mobile_confirm_order",
                    payload,
                    entity_type="order",
                    entity_id=result.get("order_id"),
                    after=result,
                    summary=f"Mobile confirmed draft {confirm_id} to order {result.get('order_id')}",
                    source_path=path,
                )
            self.send_json(result if result else {"error": "draft_not_found"}, HTTPStatus.OK if result else HTTPStatus.NOT_FOUND)
            return
        self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        payload = self.read_json()
        mobile_draft_id = self.match_dispatch_mobile_draft_path(path)
        if mobile_draft_id:
            draft = update_dispatcher_draft(mobile_draft_id, payload)
            self.send_json({"draft": draft} if draft else {"error": "draft_not_found"}, HTTPStatus.OK if draft else HTTPStatus.NOT_FOUND)
            return
        user = self.require_api_user()
        if not user:
            return
        log_operation("PUT", path, payload, self.actor_label())
        workflow_rule_id = self.match_workflow_rule_path(path)
        if workflow_rule_id:
            self.safe_update(lambda: update_rule(workflow_rule_id, payload), "rule", "rule_not_found")
            return
        org_member_id = self.match_org_member_path(path)
        if org_member_id:
            if not self.require_role({"admin"}):
                return
            self.safe_update(lambda: update_member(org_member_id, payload), "member", "member_not_found")
            return
        account_id = self._match_prefixed_id(path, "/api/accounts/")
        if account_id:
            if not self.require_role({"admin"}):
                return
            self.safe_update(lambda: update_account(account_id, payload, self.actor_label()), "account", "account_not_found")
            return
        driver_id = self.match_resource_path(path, "drivers")
        if driver_id:
            self.safe_update(lambda: update_driver(driver_id, payload), "driver", "driver_not_found")
            return
        vehicle_id = self.match_resource_path(path, "vehicles")
        if vehicle_id:
            self.safe_update(lambda: update_vehicle(vehicle_id, payload), "vehicle", "vehicle_not_found")
            return
        vehicle_record_id = self._match_prefixed_id(path, "/api/resources/vehicle-inspection-records/")
        if vehicle_record_id:
            self.safe_update(lambda: update_vehicle_inspection_record(vehicle_record_id, payload), "record", "record_not_found")
            return
        agency_id = self.match_agency_path(path)
        if agency_id:
            self.safe_update(lambda: update_agency(agency_id, payload), "agency", "agency_not_found")
            return
        if path == "/api/settings/reminders":
            self.send_json({"settings": update_reminder_settings(payload)})
            return
        draft_id = self.match_parser_draft_path(path)
        if draft_id:
            self.safe_update(lambda: update_draft(draft_id, payload), "draft", "draft_not_found")
            return
        mobile_draft_id = self.match_dispatch_mobile_draft_path(path)
        if mobile_draft_id:
            draft = update_dispatcher_draft(mobile_draft_id, payload)
            self.send_json({"draft": draft} if draft else {"error": "draft_not_found"}, HTTPStatus.OK if draft else HTTPStatus.NOT_FOUND)
            return
        order_id = self.match_order_path(path)
        if order_id:
            self.update_order_with_audit(order_id, payload, path)
            return
        finance_expense_id = self._match_prefixed_id(path, "/api/finance/driver-expenses/")
        if finance_expense_id:
            if not self.require_role({"admin"}):
                return
            if not is_feature_enabled("finance"):
                self.send_json({"error": "feature_not_enabled", "feature": "finance"}, HTTPStatus.FORBIDDEN)
                return
            self.update_driver_expense_with_audit(finance_expense_id, payload, path)
            return
        finance_order_id = self._match_prefixed_id(path, "/api/finance/orders/")
        if finance_order_id:
            if not self.require_role({"admin"}):
                return
            if not is_feature_enabled("finance"):
                self.send_json({"error": "feature_not_enabled", "feature": "finance"}, HTTPStatus.FORBIDDEN)
                return
            self.update_finance_with_audit(finance_order_id, payload, path)
            return
        self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        user = self.require_api_user()
        if not user:
            return
        log_operation("DELETE", path, {}, self.actor_label())
        draft_id = self.match_parser_draft_path(path)
        if draft_id:
            draft = discard_draft(draft_id)
            self.send_json({"deleted": True, "draft": draft} if draft else {"error": "draft_not_found"}, HTTPStatus.OK if draft else HTTPStatus.NOT_FOUND)
            return
        order_id = self.match_order_path(path)
        if order_id:
            before = get_order(order_id)
            deleted = soft_delete_order(order_id)
            if deleted:
                record_audit(
                    "order_soft_delete",
                    "order",
                    order_id,
                    before=before,
                    after={**(before or {}), "is_deleted": 1},
                    actor=self.actor_label(),
                    source_path=path,
                    summary=f"Soft deleted order {order_id}",
                )
            self.send_json({"deleted": True} if deleted else {"error": "order_not_found"}, HTTPStatus.OK if deleted else HTTPStatus.NOT_FOUND)
            return
        driver_id = self.match_resource_path(path, "drivers")
        if driver_id:
            deleted = delete_driver(driver_id)
            self.send_json({"deleted": True} if deleted else {"error": "driver_not_found"}, HTTPStatus.OK if deleted else HTTPStatus.NOT_FOUND)
            return
        vehicle_id = self.match_resource_path(path, "vehicles")
        if vehicle_id:
            deleted = delete_vehicle(vehicle_id)
            self.send_json({"deleted": True} if deleted else {"error": "vehicle_not_found"}, HTTPStatus.OK if deleted else HTTPStatus.NOT_FOUND)
            return
        vehicle_record_id = self._match_prefixed_id(path, "/api/resources/vehicle-inspection-records/")
        if vehicle_record_id:
            deleted = delete_vehicle_inspection_record(vehicle_record_id)
            self.send_json({"deleted": True} if deleted else {"error": "record_not_found"}, HTTPStatus.OK if deleted else HTTPStatus.NOT_FOUND)
            return
        agency_id = self.match_agency_path(path)
        if agency_id:
            deleted = delete_agency(agency_id)
            self.send_json({"deleted": True} if deleted else {"error": "agency_not_found"}, HTTPStatus.OK if deleted else HTTPStatus.NOT_FOUND)
            return
        self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def driver_id(self, params: dict) -> int:
        user = get_user_by_token(self.bearer_token())
        if user and user.get("role") == "driver":
            return int(user.get("profile_id") or 0)
        return int(params.get("driver_id") or self.headers.get("X-Driver-Id") or 0)

    def actor_label(self) -> str:
        user = get_user_by_token(self.bearer_token())
        if user:
            return f"{user.get('role')}:{user.get('username')}"
        driver_id = self.headers.get("X-Driver-Id")
        return f"driver:{driver_id}" if driver_id else "anonymous"

    def require_api_user(self) -> dict | None:
        user = get_user_by_token(self.bearer_token())
        if not user:
            self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return None
        set_current_tenant_id(user.get("tenant_id"))
        return user

    def require_role(self, allowed_roles: set[str]) -> dict | None:
        user = self.require_api_user()
        if not user:
            return None
        if user.get("role") not in allowed_roles:
            self.send_json({"error": "forbidden", "required_roles": sorted(allowed_roles)}, HTTPStatus.FORBIDDEN)
            return None
        return user

    def sanitize_evidence_chain(self, evidence_chain: dict | None, user: dict | None) -> dict | None:
        if not evidence_chain or (user or {}).get("role") == "admin":
            return evidence_chain
        sanitized = dict(evidence_chain)
        sanitized["expenses"] = []
        sanitized["timeline"] = [
            self._strip_money_fields(item)
            for item in evidence_chain.get("timeline", [])
            if item.get("kind") != "expense"
        ]
        sanitized["download_files"] = [
            item
            for item in evidence_chain.get("download_files", [])
            if "expense" not in str(item.get("kind") or "").lower()
            and "expense" not in str(item.get("label") or "").lower()
            and "receipt" not in str(item.get("kind") or "").lower()
            and "receipt" not in str(item.get("label") or "").lower()
        ]
        summary = dict(evidence_chain.get("summary") or {})
        for key in list(summary):
            if "expense" in key or "amount" in key or "salary" in key or "fee" in key:
                summary[key] = 0
        sanitized["summary"] = summary
        return sanitized

    def _strip_money_fields(self, item: dict) -> dict:
        row = dict(item)
        for key in ("amount", "currency", "price", "fee", "driver_salary_jpy"):
            row.pop(key, None)
        return row

    def visible_notifications(self, user: dict, params: dict | None = None) -> list[dict]:
        params = params or {}
        role = user.get("role")
        if role == "driver":
            return self.sanitize_notifications(list_driver_notifications(user.get("profile_id"), params), user)
        return self.sanitize_notifications(list_notifications(params), user)

    def sanitize_notifications(self, notifications: list[dict], user: dict | None) -> list[dict]:
        role = (user or {}).get("role")
        if role in {"admin", "dispatcher"}:
            return notifications
        if role == "operations_manager":
            allowed_types = {"resource_reminder", "incident"}
            return [
                item for item in notifications
                if str(item.get("notification_type") or item.get("type") or "").lower() in allowed_types
            ]
        if role == "driver":
            allowed_types = {"new_order", "upcoming_start", "delay_risk"}
            return [
                item for item in notifications
                if str(item.get("target_role") or "").lower() == "driver"
                and str(item.get("notification_type") or item.get("type") or "").lower() in allowed_types
            ]
        blocked_types = {"pending_driver_expense", "finance", "billing", "salary", "reimbursement"}
        rows = []
        for item in notifications:
            notification_type = str(item.get("notification_type") or item.get("type") or "").lower()
            source_type = str(item.get("source_type") or "").lower()
            link = str(item.get("link") or "").lower()
            if notification_type in blocked_types:
                continue
            if any(keyword in source_type or keyword in link for keyword in ("expense", "finance", "billing", "salary", "reimburse")):
                continue
            rows.append(item)
        return rows

    def create_order_with_audit(self, payload: dict, path: str) -> None:
        try:
            order = create_order(payload)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        record_audit(
            "order_create",
            "order",
            order.get("id") or order.get("oid"),
            after=order,
            actor=self.actor_label(),
            source_path=path,
            summary=f"Created order {order.get('oid') or order.get('id')}",
        )
        self.send_json({"order": order}, HTTPStatus.CREATED)

    def update_order_with_audit(self, order_id: str, payload: dict, path: str) -> None:
        before = get_order(order_id)
        if not before:
            self.send_json({"error": "order_not_found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            order = update_order(order_id, payload)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if order:
            record_audit(
                "order_update",
                "order",
                order.get("id") or order_id,
                before=before,
                after=order,
                actor=self.actor_label(),
                source_path=path,
                summary=f"Updated order {order.get('oid') or order_id}",
            )
        self.send_json({"order": order} if order else {"error": "order_not_found"}, HTTPStatus.OK if order else HTTPStatus.NOT_FOUND)

    def update_finance_with_audit(self, order_id: str, payload: dict, path: str) -> None:
        before = get_order(order_id)
        if not before:
            self.send_json({"error": "order_not_found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            order = update_settlement(order_id, payload)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if order:
            after = get_order(order_id) or order
            record_audit(
                "finance_update",
                "order",
                order.get("id") or order_id,
                before=before,
                after=after,
                actor=self.actor_label(),
                source_path=path,
                summary=f"Updated finance fields for order {order.get('oid') or order_id}",
            )
        self.send_json({"order": order} if order else {"error": "order_not_found"}, HTTPStatus.OK if order else HTTPStatus.NOT_FOUND)

    def update_driver_expense_with_audit(self, expense_id: str, payload: dict, path: str) -> None:
        before = get_finance_driver_expense(expense_id)
        if not before:
            self.send_json({"error": "driver_expense_not_found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            expense = update_finance_driver_expense(expense_id, payload)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if expense:
            record_audit(
                "finance_driver_expense_update",
                "driver_expense",
                expense.get("id") or expense_id,
                before=before,
                after=expense,
                actor=self.actor_label(),
                source_path=path,
                summary=f"Updated driver expense {expense.get('id') or expense_id} to {expense.get('submit_status')}",
            )
        self.send_json({"expense": expense} if expense else {"error": "driver_expense_not_found"}, HTTPStatus.OK if expense else HTTPStatus.NOT_FOUND)

    def dispatch_assign_with_audit(self, payload: dict, path: str) -> None:
        try:
            result = assign_orders(payload.get("order_ids", []), payload.get("driver_id"), payload.get("vehicle_id"))
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        entity_id = ",".join(str(item) for item in result.get("assignment_ids", [])) or ",".join(str(item) for item in payload.get("order_ids", []))
        record_audit(
            "dispatch_assign",
            "assignment",
            entity_id,
            after={"payload": payload, "result": result},
            actor=self.actor_label(),
            source_path=path,
            summary=f"Assigned {len(result.get('updated_order_ids', []))} order(s)",
        )
        record_dispatch_mobile_audit(
            "mobile_dispatch_assign",
            payload,
            entity_type="assignment",
            entity_id=entity_id,
            after=result,
            summary=f"Mobile assigned {len(result.get('updated_order_ids', []))} order(s)",
            source_path=path,
        )
        self.send_json(result)

    def dispatch_cancel_with_audit(self, payload: dict, path: str) -> None:
        result = cancel_assignment(payload.get("assignment_id"), payload.get("order_id"))
        if result.get("success"):
            record_audit(
                "dispatch_cancel",
                "assignment",
                result.get("cancelled_assignment_id") or payload.get("assignment_id") or payload.get("order_id"),
                after={"payload": payload, "result": result},
                actor=self.actor_label(),
                source_path=path,
                summary=f"Cancelled assignment {result.get('cancelled_assignment_id')}",
            )
        self.send_json(result)

    def dispatch_reassign_with_audit(self, payload: dict, path: str) -> None:
        try:
            result = reassign_orders(payload.get("order_ids", []), payload.get("new_driver_id"), payload.get("new_vehicle_id"))
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        entity_id = ",".join(str(item) for item in result.get("new_assignment_ids", [])) or ",".join(str(item) for item in payload.get("order_ids", []))
        record_audit(
            "dispatch_reassign",
            "assignment",
            entity_id,
            after={"payload": payload, "result": result},
            actor=self.actor_label(),
            source_path=path,
            summary=f"Reassigned {len(result.get('updated_order_ids', []))} order(s)",
        )
        self.send_json(result)

    def safe_create(self, func, status: HTTPStatus = HTTPStatus.OK) -> None:
        try:
            self.send_json(func(), status)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def safe_update(self, func, key: str, error: str) -> None:
        try:
            result = func()
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        self.send_json({key: result} if result else {"error": error}, HTTPStatus.OK if result else HTTPStatus.NOT_FOUND)

    def safe_agency(self, func, status: HTTPStatus = HTTPStatus.OK) -> None:
        try:
            self.send_json(func(), status)
        except ValueError as exc:
            code = HTTPStatus.UNAUTHORIZED if str(exc) == "agency_unauthorized" else HTTPStatus.BAD_REQUEST
            self.send_json({"error": str(exc)}, code)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def bearer_token(self) -> str:
        auth = self.headers.get("Authorization", "")
        return auth.removeprefix("Bearer ").strip() if auth.startswith("Bearer ") else ""

    def agency_token(self) -> str:
        token = self.headers.get("X-Agency-Token", "")
        return token.strip() if token else self.bearer_token()

    def query_params(self, query: str) -> dict:
        parsed = parse_qs(query, keep_blank_values=False)
        return {key: values[-1] for key, values in parsed.items() if values}

    def send_driver_google_map_page(self, params: dict) -> None:
        pickup = (params.get("pickup") or "").strip()
        dropoff = (params.get("dropoff") or "").strip()
        pickup_lat = (params.get("pickup_latitude") or "").strip()
        pickup_lng = (params.get("pickup_longitude") or "").strip()
        dropoff_lat = (params.get("dropoff_latitude") or "").strip()
        dropoff_lng = (params.get("dropoff_longitude") or "").strip()

        origin = f"{pickup_lat},{pickup_lng}" if pickup_lat and pickup_lng else pickup
        destination = f"{dropoff_lat},{dropoff_lng}" if dropoff_lat and dropoff_lng else dropoff
        if origin and destination:
            embed_url = f"https://maps.google.com/maps?saddr={quote(origin)}&daddr={quote(destination)}&output=embed"
            open_url = (
                "https://www.google.com/maps/dir/?api=1"
                f"&origin={quote(origin)}&destination={quote(destination)}&travelmode=driving"
            )
        else:
            query = origin or destination or "Japan"
            embed_url = f"https://maps.google.com/maps?q={quote(query)}&output=embed"
            open_url = f"https://www.google.com/maps/search/?api=1&query={quote(query)}"

        html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
  <title>Google Maps 导航</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f7fb; color: #0f172a; }}
    .page {{ min-height: 100vh; display: flex; flex-direction: column; }}
    .header {{ padding: 14px 16px 12px; background: #0f172a; color: #fff; }}
    .title {{ font-size: 18px; font-weight: 800; }}
    .route {{ margin-top: 8px; font-size: 13px; color: #dbeafe; line-height: 1.5; }}
    .map {{ flex: 1; min-height: 65vh; background: #e2e8f0; }}
    iframe {{ width: 100%; height: 100%; min-height: 65vh; border: 0; display: block; }}
    .actions {{ padding: 12px 16px 18px; display: grid; gap: 10px; background: #fff; box-shadow: 0 -8px 24px rgba(15,23,42,.08); }}
    .button {{ display: block; text-align: center; text-decoration: none; border-radius: 14px; padding: 13px 14px; font-weight: 800; }}
    .primary {{ background: #2563eb; color: #fff; }}
    .secondary {{ background: #eff6ff; color: #1d4ed8; }}
    .hint {{ font-size: 12px; color: #64748b; text-align: center; line-height: 1.5; }}
  </style>
</head>
<body>
  <div class="page">
    <div class="header">
      <div class="title">Google Maps 导航</div>
      <div class="route">上车点：{escape(pickup or "-")}<br>终点：{escape(dropoff or "-")}</div>
    </div>
    <div class="map">
      <iframe src="{escape(embed_url)}" allowfullscreen loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
    </div>
    <div class="actions">
      <a class="button primary" href="{escape(open_url)}">在 Google Maps 打开导航</a>
      <a class="button secondary" href="https://www.google.com/maps/search/?api=1&query={quote(pickup or dropoff or 'Japan')}">搜索上车点</a>
      <div class="hint">如果嵌入地图未显示，请点上方按钮打开 Google Maps。小程序正式版需要配置 web-view 业务域名。</div>
    </div>
  </div>
</body>
</html>"""
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def parse_ids(self, value: str) -> list[int]:
        return [int(item.strip()) for item in value.split(",") if item.strip().isdigit()]

    def match_order_path(self, path: str) -> str:
        return self._match_prefixed_id(path, "/api/orders/")

    def match_calendar_detail_path(self, path: str) -> str:
        return self._match_prefixed_id(path, "/api/calendar/dispatch/detail/")

    def match_parser_draft_path(self, path: str) -> str:
        if path.endswith("/confirm"):
            return ""
        return self._match_prefixed_id(path, "/api/parser/drafts/")

    def match_parser_confirm_path(self, path: str) -> str:
        prefix, suffix = "/api/parser/drafts/", "/confirm"
        if not path.startswith(prefix) or not path.endswith(suffix):
            return ""
        return path.removeprefix(prefix).removesuffix(suffix).strip("/")

    def match_dispatch_mobile_draft_path(self, path: str) -> str:
        return self._match_prefixed_id(path, "/api/dispatch-mobile/drafts/")

    def match_dispatch_mobile_confirm_path(self, path: str) -> str:
        prefix, suffix = "/api/dispatch-mobile/drafts/", "/confirm"
        if not path.startswith(prefix) or not path.endswith(suffix):
            return ""
        return path.removeprefix(prefix).removesuffix(suffix).strip("/")

    def match_dispatch_mobile_order_update_path(self, path: str) -> str:
        prefix, suffix = "/api/dispatch-mobile/orders/", "/update"
        if not path.startswith(prefix) or not path.endswith(suffix):
            return ""
        return path.removeprefix(prefix).removesuffix(suffix).strip("/")

    def match_incident_close_path(self, path: str) -> str:
        prefix, suffix = "/api/incidents/", "/close"
        if not path.startswith(prefix) or not path.endswith(suffix):
            return ""
        return path.removeprefix(prefix).removesuffix(suffix).strip("/")

    def match_resource_path(self, path: str, resource: str) -> str:
        return self._match_prefixed_id(path, f"/api/resources/{resource}/")

    def match_agency_path(self, path: str) -> str:
        return self._match_prefixed_id(path, "/api/agencies/")

    def match_org_member_path(self, path: str) -> str:
        return self._match_prefixed_id(path, "/api/org/members/")

    def match_org_disable_path(self, path: str) -> str:
        prefix, suffix = "/api/org/members/", "/disable"
        if not path.startswith(prefix) or not path.endswith(suffix):
            return ""
        return path.removeprefix(prefix).removesuffix(suffix).strip("/")

    def match_notification_read_path(self, path: str) -> str:
        prefix, suffix = "/api/notifications/", "/read"
        if not path.startswith(prefix) or not path.endswith(suffix):
            return ""
        return path.removeprefix(prefix).removesuffix(suffix).strip("/")

    def match_workflow_rule_path(self, path: str) -> str:
        return self._match_prefixed_id(path, "/api/workflows/rules/")

    def match_driver_assignment_path(self, path: str) -> str:
        return self._match_prefixed_id(path, "/api/driver/assignments/")

    def match_assignment_evidence_path(self, path: str) -> str:
        prefix, suffix = "/api/assignments/", "/evidence"
        if not path.startswith(prefix) or not path.endswith(suffix):
            return ""
        value = path.removeprefix(prefix).removesuffix(suffix).strip("/")
        return value if value and "/" not in value else ""

    def match_order_evidence_path(self, path: str) -> str:
        prefix, suffix = "/api/orders/", "/evidence"
        if not path.startswith(prefix) or not path.endswith(suffix):
            return ""
        value = path.removeprefix(prefix).removesuffix(suffix).strip("/")
        return value if value and "/" not in value else ""

    def match_driver_notification_read_path(self, path: str) -> str:
        prefix, suffix = "/api/driver/notifications/", "/read"
        if not path.startswith(prefix) or not path.endswith(suffix):
            return ""
        return path.removeprefix(prefix).removesuffix(suffix).strip("/")

    def _match_action_path(self, path: str, prefix: str, suffix: str) -> str:
        if not path.startswith(prefix) or not path.endswith(suffix):
            return ""
        value = path.removeprefix(prefix).removesuffix(suffix).strip("/")
        return value if value and "/" not in value else ""

    def _match_prefixed_id(self, path: str, prefix: str) -> str:
        if not path.startswith(prefix):
            return ""
        value = path.removeprefix(prefix).strip("/")
        return value if value and "/" not in value else ""

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_csv(self, text: str, filename: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = text.encode("utf-8-sig")
        self.send_response(status.value)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_frontend_asset(self, path: str) -> bool:
        if path.startswith("/api/"):
            return False
        if not FRONTEND_DIST_DIR.exists():
            if path in {"/", "/dashboard"}:
                self.send_dashboard_page()
                return True
            return False

        relative = path.lstrip("/")
        if not relative or relative == "dashboard":
            target = FRONTEND_DIST_DIR / "index.html"
        else:
            target = FRONTEND_DIST_DIR / relative
            if not target.exists() and "." not in Path(relative).name:
                target = FRONTEND_DIST_DIR / "index.html"

        try:
            resolved = target.resolve()
            dist_root = FRONTEND_DIST_DIR.resolve()
            if not str(resolved).startswith(str(dist_root)) or not resolved.is_file():
                return False
            body = resolved.read_bytes()
        except OSError:
            return False

        content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
        if resolved.name == "index.html":
            content_type = "text/html; charset=utf-8"
        elif content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
            content_type = f"{content_type}; charset=utf-8"

        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return True

    def serve_upload_asset(self, path: str) -> bool:
        if not path.startswith("/uploads/"):
            return False
        relative = path.removeprefix("/uploads/").strip("/")
        if not relative:
            return False
        target = UPLOAD_DIR / relative
        try:
            resolved = target.resolve()
            upload_root = UPLOAD_DIR.resolve()
            if not str(resolved).startswith(str(upload_root)) or not resolved.is_file():
                return False
            body = resolved.read_bytes()
        except OSError:
            return False
        content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return True

    def send_dashboard_page(self) -> None:
        summary = get_summary()
        cards = [
            ("今日订单", "today_orders"),
            ("已派车", "assigned_orders"),
            ("待确认草稿", "pending_drafts"),
            ("已确认", "today_confirmed_orders"),
            ("已出库", "today_departed_orders"),
            ("已到达", "today_arrived_orders"),
            ("服务中", "today_in_service_orders"),
            ("已完成", "today_completed_orders"),
            ("已归库", "today_returned_orders"),
            ("未报备", "unreported_assignments"),
        ]
        card_html = "".join(f'<div class="card"><div class="label">{label}</div><div class="value">{summary.get(key, 0)}</div></div>' for label, key in cards)
        html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8" /><title>微信调度运营中台</title>
<style>body{{margin:0;font-family:Arial,'Microsoft YaHei',sans-serif;background:#f6f7f9;color:#20242a}}.layout{{display:flex;min-height:100vh}}aside{{width:180px;background:#1f2933;color:#fff;padding:24px 18px}}main{{flex:1;padding:28px}}.cards{{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:14px}}.card{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:18px}}.label{{color:#5b6472;font-size:14px}}.value{{font-size:30px;font-weight:700;margin-top:8px}}</style></head>
<body><div class="layout"><aside><strong>调度中台</strong></aside><main><h1>首页</h1><section class="cards">{card_html}</section></main></div></body></html>"""
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_dashboard_page(self) -> None:
        summary = get_summary()
        orders = list_orders({})[:10]
        assignments = list_assignments("active")[:10]
        drafts = list_drafts()[:8]
        calendar = get_dispatch_calendar({"view": "day", "date": summary.get("date", "")})
        calendar_items = calendar.get("items", [])[:12]

        def safe(value) -> str:
            if value is None or value == "":
                return "-"
            return escape(str(value))

        def status_badge(value) -> str:
            status = safe(value)
            return f'<span class="badge">{status}</span>'

        kpis = [
            ("今日订单", "today_orders", "blue"),
            ("今日已派车", "today_assigned_orders", "green"),
            ("今日执行中", "today_in_service_orders", "purple"),
            ("今日已完成", "today_completed_orders", "gray"),
            ("待确认草稿", "pending_drafts", "orange"),
            ("未派车订单", "today_unassigned_orders", "red"),
            ("未报备订单", "unreported_assignments", "orange"),
            ("解析失败", "failed_drafts", "red"),
        ]
        kpi_html = "".join(
            f'<div class="kpi {tone}"><div class="kpi-label">{label}</div><div class="kpi-value">{summary.get(key, 0)}</div></div>'
            for label, key, tone in kpis
        )

        order_rows = "".join(
            "<tr>"
            f"<td>{safe(order.get('order_date'))}<small>{safe(order.get('start_time'))}-{safe(order.get('end_time'))}</small></td>"
            f"<td><b>{safe(order.get('pickup_location'))}</b><small>{safe(order.get('dropoff_location'))}</small></td>"
            f"<td>{safe(order.get('order_type'))}<small>{safe(order.get('vehicle_type'))}</small></td>"
            f"<td>{safe(order.get('agency_name'))}</td>"
            f"<td>{safe(order.get('price'))}</td>"
            f"<td>{status_badge(order.get('dispatch_status'))}</td>"
            f"<td>{status_badge(order.get('execution_status'))}</td>"
            "</tr>"
            for order in orders
        ) or '<tr><td colspan="7" class="empty">暂无订单数据</td></tr>'

        assignment_rows = "".join(
            "<tr>"
            f"<td>{safe(item.get('order_date'))}<small>{safe(item.get('start_time'))}-{safe(item.get('end_time'))}</small></td>"
            f"<td><b>{safe(item.get('pickup_location'))}</b><small>{safe(item.get('dropoff_location'))}</small></td>"
            f"<td>{safe(item.get('driver_name'))}</td>"
            f"<td>{safe(item.get('plate_number'))}<small>{safe(item.get('vehicle_type'))}</small></td>"
            f"<td>{status_badge(item.get('execution_status'))}</td>"
            f"<td>{safe(item.get('latest_report_time'))}<small>{safe(item.get('latest_location_text'))}</small></td>"
            "</tr>"
            for item in assignments
        ) or '<tr><td colspan="6" class="empty">暂无派车记录</td></tr>'

        calendar_html = "".join(
            f'<div class="event" style="border-left-color:{safe(item.get("calendar_color"))}">'
            f'<div><b>{safe(item.get("plate_number"))}</b><span>{safe(item.get("start_time"))}-{safe(item.get("end_time"))}</span></div>'
            f'<p>{safe(item.get("pickup_location"))} -> {safe(item.get("dropoff_location"))}</p>'
            f'<small>{safe(item.get("driver_name"))} · {safe(item.get("display_subtitle"))}</small>'
            "</div>"
            for item in calendar_items
        ) or '<div class="empty block">今日日历暂无派车</div>'

        draft_rows = "".join(
            "<tr>"
            f"<td>{safe(draft.get('raw_text'))}</td>"
            f"<td>{safe(draft.get('order_date'))}<small>{safe(draft.get('start_time'))}</small></td>"
            f"<td>{safe(draft.get('pickup_location'))}<small>{safe(draft.get('dropoff_location'))}</small></td>"
            f"<td>{status_badge(draft.get('parse_status'))}</td>"
            "</tr>"
            for draft in drafts
        ) or '<tr><td colspan="4" class="empty">暂无解析草稿</td></tr>'

        html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>调度运营中台</title>
  <style>
    *{{box-sizing:border-box}} body{{margin:0;font-family:Arial,'Microsoft YaHei',sans-serif;background:#f3f5f8;color:#17202a}}
    .layout{{display:flex;min-height:100vh}} aside{{width:220px;background:#172433;color:#fff;padding:24px 20px;position:sticky;top:0;height:100vh}}
    .brand{{font-size:22px;font-weight:800;line-height:1.35;margin-bottom:28px}} .nav a{{display:block;color:#d8e2ee;text-decoration:none;padding:11px 12px;border-radius:6px;margin:4px 0;font-size:15px}}
    .nav a:hover,.nav a.active{{background:#24384e;color:#fff}} main{{flex:1;padding:26px 30px 42px;max-width:1440px}}
    .top{{display:flex;align-items:flex-end;justify-content:space-between;margin-bottom:18px}} h1{{font-size:34px;margin:0 0 6px}} .sub{{color:#667085;font-size:14px}}
    .actions span{{display:inline-block;background:#fff;border:1px solid #dce3ec;border-radius:18px;padding:8px 12px;margin-left:8px;color:#344054;font-size:13px}}
    .kpis{{display:grid;grid-template-columns:repeat(4,minmax(160px,1fr));gap:14px;margin-bottom:18px}} .kpi{{background:#fff;border:1px solid #dde5ee;border-radius:8px;padding:16px;box-shadow:0 1px 2px rgba(16,24,40,.04)}}
    .kpi-label{{color:#526071;font-size:14px}} .kpi-value{{font-size:32px;font-weight:800;margin-top:8px}} .blue{{border-top:4px solid #2f80ed}} .green{{border-top:4px solid #219653}} .purple{{border-top:4px solid #7b61ff}} .orange{{border-top:4px solid #f2994a}} .red{{border-top:4px solid #eb5757}} .gray{{border-top:4px solid #98a2b3}}
    .notice{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:18px}} .notice div{{background:#fff;border:1px solid #dde5ee;border-radius:8px;padding:14px 16px}} .notice b{{font-size:22px;margin-right:6px}}
    .grid{{display:grid;grid-template-columns:1.25fr .9fr;gap:16px;align-items:start}} .panel{{background:#fff;border:1px solid #dde5ee;border-radius:8px;padding:16px;margin-bottom:16px}}
    .panel h2{{font-size:18px;margin:0 0 12px;display:flex;justify-content:space-between;align-items:center}} .panel h2 small{{color:#667085;font-size:12px;font-weight:400}}
    table{{width:100%;border-collapse:collapse}} th{{text-align:left;color:#667085;font-size:12px;font-weight:700;border-bottom:1px solid #e6ebf1;padding:9px 8px}} td{{border-bottom:1px solid #edf1f5;padding:10px 8px;vertical-align:top;font-size:14px}} td small{{display:block;color:#667085;margin-top:4px}} td b{{font-weight:700}}
    .badge{{display:inline-block;background:#eef3f8;border:1px solid #dce5ef;border-radius:14px;padding:4px 8px;color:#344054;font-size:12px}} .empty{{color:#98a2b3;text-align:center;padding:22px}} .block{{border:1px dashed #d0d5dd;border-radius:8px}}
    .event{{border-left:5px solid #2f80ed;background:#f8fafc;border-radius:7px;padding:10px 12px;margin-bottom:10px}} .event div{{display:flex;justify-content:space-between;gap:12px}} .event p{{margin:7px 0 4px;font-weight:700}} .event small{{color:#667085}}
    .flow{{display:flex;flex-wrap:wrap;gap:8px}} .flow span{{background:#f2f4f7;border:1px solid #d0d5dd;border-radius:16px;padding:7px 10px;font-size:13px}} .hint{{color:#667085;font-size:13px;line-height:1.7;margin:0}}
    @media(max-width:1000px){{aside{{width:88px;padding:20px 10px}}.brand{{font-size:18px;text-align:center}}.nav a{{text-align:center;font-size:13px}}main{{padding:20px}}.kpis,.notice,.grid{{grid-template-columns:1fr}}}}
  <style>
    #pending table{table-layout:fixed;min-width:1120px}
    #pending th:nth-child(1){width:46px}
    #pending th:nth-child(2){width:126px}
    #pending th:nth-child(3),#pending th:nth-child(4){width:150px}
    #pending th:nth-child(5){width:190px}
    #pending th:nth-child(6){width:96px}
    #pending th:nth-child(7){width:110px}
    #pending th:nth-child(8){width:96px}
    #pending th:nth-child(9){width:168px}
    #pending th:nth-child(10){width:138px}
    #pending td{height:48px}
    .text-cell,.ellipsis{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .muted{color:#667085}
    .op-cell{white-space:nowrap}
    .link-btn{height:auto;background:transparent;color:#2563eb;padding:0 5px;border:0}
    .detail-row td{background:#fbfdff;height:auto}
    .detail-box{display:grid;grid-template-columns:repeat(4,minmax(160px,1fr));gap:8px;color:#334155;line-height:1.5}
    .detail-box b,.detail-box p{grid-column:1/-1;margin:0}
  </style>
  </style>
</head>
<body>
  <div class="layout">
    <aside>
      <div class="brand">调度<br>中台</div>
      <nav class="nav">
        <a class="active" href="#overview">总览</a>
        <a href="#orders">订单</a>
        <a href="#dispatch">派车</a>
        <a href="#calendar">日历</a>
        <a href="#drafts">草稿</a>
        <a href="#driver">司机端</a>
      </nav>
    </aside>
    <main>
      <section class="top" id="overview">
        <div><h1>调度运营中台</h1><div class="sub">MVP 演示模式 · 数据来自 orders / assignments / drivers / vehicles / drafts</div></div>
        <div class="actions"><span>日期 {safe(summary.get("date"))}</span><span>原生小程序骨架</span></div>
      </section>
      <section class="kpis">{kpi_html}</section>
      <section class="notice">
        <div><b>{summary.get("today_unassigned_orders", 0)}</b>单今日未派车，优先进入派车页处理。</div>
        <div><b>{summary.get("unreported_assignments", 0)}</b>单未报备，司机端需要继续执行状态。</div>
        <div><b>{summary.get("pending_drafts", 0)}</b>条草稿待确认，解析录单后需人工入库。</div>
      </section>
      <section class="grid">
        <div>
          <div class="panel" id="orders"><h2>订单大表 <small>最近 10 单</small></h2><table><thead><tr><th>日期时间</th><th>路线</th><th>类型/车型</th><th>旅行社</th><th>价格</th><th>派车</th><th>执行</th></tr></thead><tbody>{order_rows}</tbody></table></div>
          <div class="panel" id="dispatch"><h2>派车执行 <small>active assignments</small></h2><table><thead><tr><th>日期时间</th><th>路线</th><th>司机</th><th>车辆</th><th>状态</th><th>最新报备</th></tr></thead><tbody>{assignment_rows}</tbody></table></div>
        </div>
        <div>
          <div class="panel" id="calendar"><h2>今日日历 <small>车辆派车卡片</small></h2>{calendar_html}</div>
          <div class="panel" id="drafts"><h2>解析草稿 <small>最近 8 条</small></h2><table><thead><tr><th>原文</th><th>时间</th><th>路线</th><th>状态</th></tr></thead><tbody>{draft_rows}</tbody></table></div>
          <div class="panel" id="driver"><h2>司机端演示 <small>/api/driver?driver_id</small></h2><p class="hint">司机端采用轻量身份参数 driver_id。演示顺序是查看我的订单，按下一步按钮完成确认、出库、到达、开始服务、完成、归库。</p><div class="flow"><span>确认订单</span><span>出库</span><span>到达</span><span>开始服务</span><span>完成</span><span>归库</span></div></div>
        </div>
      </section>
    </main>
  </div>
</body>
</html>"""
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_dashboard_page(self) -> None:
        html = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>调度工作台</title>
  <style>
    *{box-sizing:border-box} body{margin:0;font-family:Arial,'Microsoft YaHei',sans-serif;background:#eef2f6;color:#17202a}
    .layout{display:flex;min-height:100vh}.side{width:208px;background:#172433;color:#fff;padding:24px 18px;position:sticky;top:0;height:100vh}
    .brand{font-size:22px;font-weight:800;line-height:1.35;margin-bottom:28px}.nav a{display:block;color:#d8e2ee;text-decoration:none;padding:11px 12px;border-radius:6px;margin:4px 0;font-size:15px}.nav a.active{background:#27415d;color:#fff}
    main{flex:1;padding:22px 26px 44px}.top{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:14px}h1{margin:0;font-size:30px}.sub{color:#667085;margin-top:6px}.pill{background:#fff;border:1px solid #d8e0ea;border-radius:18px;padding:8px 12px;color:#344054;font-size:13px}
    .kpis{display:grid;grid-template-columns:repeat(6,minmax(120px,1fr));gap:10px;margin-bottom:14px}.kpi{background:#fff;border:1px solid #d8e0ea;border-radius:8px;padding:12px}.kpi b{display:block;font-size:25px;margin-top:5px}.kpi span{color:#667085;font-size:13px}
    .workspace{display:grid;grid-template-columns:minmax(560px,1.15fr) minmax(420px,.85fr);gap:14px;align-items:start}.panel{background:#fff;border:1px solid #d8e0ea;border-radius:8px;padding:14px;margin-bottom:14px;box-shadow:0 1px 2px rgba(16,24,40,.04)}
    .panel h2{font-size:18px;margin:0 0 12px;display:flex;justify-content:space-between;align-items:center}.panel h2 small{font-size:12px;color:#667085;font-weight:400}
    textarea,input,select{width:100%;border:1px solid #cbd5e1;border-radius:6px;padding:9px 10px;font-size:14px;background:#fff}textarea{min-height:128px;resize:vertical}.btns{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
    button{border:0;border-radius:6px;padding:9px 13px;font-weight:700;cursor:pointer;background:#1f6feb;color:#fff}button.secondary{background:#eef3f8;color:#344054;border:1px solid #cbd5e1}button.danger{background:#dc3545}.muted{color:#667085;font-size:13px}.split{display:grid;grid-template-columns:1fr 1fr;gap:10px}.triple{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
    .list{display:grid;gap:8px;max-height:430px;overflow:auto;padding-right:3px}.item{border:1px solid #e1e7ef;border-radius:7px;padding:10px;background:#fbfcfe;cursor:pointer}.item.active{border-color:#1f6feb;background:#edf5ff}.item b{display:block;font-size:15px}.item small{display:block;color:#667085;margin-top:4px;line-height:1.4}.tag{display:inline-block;background:#eef3f8;border:1px solid #d8e0ea;border-radius:13px;padding:3px 8px;color:#344054;font-size:12px;margin-top:6px}
    .resources{display:grid;grid-template-columns:1fr 1fr;gap:12px}.scroll{max-height:330px;overflow:auto;display:grid;gap:8px}.resource{border:1px solid #e1e7ef;border-radius:7px;padding:10px;background:#fbfcfe;cursor:pointer}.resource.active{border-color:#219653;background:#eefaf2}.resource b{display:block}.resource small{color:#667085}
    table{width:100%;border-collapse:collapse}th{text-align:left;color:#667085;font-size:12px;border-bottom:1px solid #e6ebf1;padding:8px}td{border-bottom:1px solid #edf1f5;padding:9px 8px;vertical-align:top;font-size:14px}td small{display:block;color:#667085;margin-top:3px}.empty{padding:18px;text-align:center;color:#98a2b3}
    .calendar{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px}.event{border-left:5px solid #2f80ed;background:#f8fafc;border-radius:7px;padding:10px}.event div{display:flex;justify-content:space-between;gap:8px}.event p{margin:6px 0;font-weight:700}.event small{color:#667085}
    .edit{display:grid;gap:10px}.toast{position:fixed;right:24px;bottom:24px;background:#172433;color:#fff;border-radius:8px;padding:12px 14px;display:none;box-shadow:0 8px 24px rgba(16,24,40,.2)}
    @media(max-width:1100px){.side{width:92px;padding:20px 10px}.brand{text-align:center;font-size:18px}.nav a{text-align:center;font-size:13px}.workspace,.resources,.kpis{grid-template-columns:1fr}main{padding:18px}}
  </style>
</head>
<body>
<div class="layout">
  <aside class="side"><div class="brand">调度<br>工作台</div><nav class="nav"><a class="active" href="#work">录单派车</a><a href="#assigned">已派订单</a><a href="#calendar">日历</a></nav></aside>
  <main>
    <section class="top"><div><h1>录单派车一体工作台</h1><div class="sub">批量输入 -> 解析草稿 -> 人工修正 -> 选司机车辆 -> 一键生成订单和日历</div></div><div class="pill" id="status">加载中</div></section>
    <section class="kpis" id="kpis"></section>
    <section class="workspace" id="work">
      <div>
        <div class="panel">
          <h2>批量输入订单 <small>一行一单，先生成草稿</small></h2>
          <textarea id="batchText" placeholder="例如：
5/24 14:10 关西接机大阪 10座600
5月7日 关西机场送大阪市内 6人 丰田海狮
羽田接机 15:30 银座 2位客人"></textarea>
          <div class="btns"><button onclick="parseBatch()">批量解析</button><button class="secondary" onclick="loadAll()">刷新数据</button></div>
        </div>
        <div class="panel">
          <h2>订单草稿 / 待派订单 <small>点中一单后在右侧修改并派车</small></h2>
          <div class="list" id="draftList"></div>
        </div>
      </div>
      <div>
        <div class="panel">
          <h2>修改并直接派单 <small id="selectedHint">未选择订单</small></h2>
          <div class="edit" id="editor"></div>
        </div>
        <div class="panel">
          <h2>选择司机和车辆 <small>上下滑动，点中即选择</small></h2>
          <div class="resources"><div><b>司机</b><div class="scroll" id="drivers"></div></div><div><b>车辆</b><div class="scroll" id="vehicles"></div></div></div>
        </div>
      </div>
    </section>
    <section class="panel" id="assigned"><h2>已经派完的订单 <small>active assignments</small></h2><table><thead><tr><th>时间</th><th>路线</th><th>司机</th><th>车辆</th><th>状态</th></tr></thead><tbody id="assignedRows"></tbody></table></section>
    <section class="panel" id="calendar"><h2>派车日历 <small>派单后自动反映到这里</small></h2><div class="calendar" id="calendarItems"></div></section>
  </main>
</div>
<div class="toast" id="toast"></div>
<script>
let state={drafts:[],orders:[],drivers:[],vehicles:[],assignments:[],calendar:[],selected:null,driver:null,vehicle:null};
const $=id=>document.getElementById(id);
function toast(msg){const el=$('toast');el.textContent=msg;el.style.display='block';setTimeout(()=>el.style.display='none',2400)}
async function api(path,opts={}){const res=await fetch(path,{headers:{'Content-Type':'application/json'},...opts});const data=await res.json();if(!res.ok)throw new Error(data.error||res.statusText);return data}
function route(x){return `${x.pickup_location||'-'} -> ${x.dropoff_location||'-'}`}
function timeText(x){return `${x.order_date||'-'} ${x.start_time||''}${x.end_time?'-'+x.end_time:''}`}
async function loadAll(){
  const [summary,drafts,orders,drivers,vehicles,assignments,cal]=await Promise.all([
    api('/api/dashboard/summary'),api('/api/parser/drafts'),api('/api/dispatch/unassigned-orders'),api('/api/dispatch/drivers'),api('/api/dispatch/vehicles'),api('/api/dispatch/assignments'),api('/api/calendar/dispatch?view=day')
  ]);
  state.drafts=(drafts.drafts||[]).filter(x=>x.parse_status!=='confirmed').slice(0,30);
  state.orders=orders.orders||[];state.drivers=drivers.drivers||[];state.vehicles=vehicles.vehicles||[];state.assignments=assignments.assignments||[];state.calendar=cal.items||[];
  renderKpis(summary);renderDrafts();renderResources();renderAssigned();renderCalendar();$('status').textContent='已连接 API';
}
function renderKpis(s){const items=[['今日订单',s.today_orders],['已派车',s.today_assigned_orders],['未派车',s.today_unassigned_orders],['待确认草稿',s.pending_drafts],['未报备',s.unreported_assignments],['可用车辆',s.available_vehicles]];$('kpis').innerHTML=items.map(i=>`<div class="kpi"><span>${i[0]}</span><b>${i[1]||0}</b></div>`).join('')}
function renderDrafts(){
  const draftCards=state.drafts.map(x=>`<div class="item ${state.selected?.kind==='draft'&&state.selected.id===x.id?'active':''}" onclick="selectDraft(${x.id})"><b>${x.raw_text||route(x)}</b><small>${timeText(x)}<br>${route(x)}</small><span class="tag">${x.parse_status}</span></div>`).join('');
  const orderCards=state.orders.map(x=>`<div class="item ${state.selected?.kind==='order'&&state.selected.id===x.id?'active':''}" onclick="selectOrder(${x.id})"><b>${route(x)}</b><small>${timeText(x)} · ${x.order_type||'-'} · ${x.vehicle_type||'-'}</small><span class="tag">待派车</span></div>`).join('');
  $('draftList').innerHTML=draftCards+orderCards || '<div class="empty">暂无草稿或待派订单</div>';
}
function selectDraft(id){const x=state.drafts.find(i=>i.id===id);state.selected={kind:'draft',id,data:{...x}};renderDrafts();renderEditor()}
function selectOrder(id){const x=state.orders.find(i=>i.id===id);state.selected={kind:'order',id,data:{...x}};renderDrafts();renderEditor()}
function field(name,label,type='text'){const v=state.selected?.data?.[name]??'';return `<label><span class="muted">${label}</span><input id="f_${name}" type="${type}" value="${String(v).replaceAll('"','&quot;')}"></label>`}
function renderEditor(){if(!state.selected){$('editor').innerHTML='<div class="empty">先点左侧一条草稿或待派订单</div>';return}
  $('selectedHint').textContent=state.selected.kind==='draft'?'草稿可修改后确认派单':'待派订单可直接派单';
  $('editor').innerHTML=`<div class="triple">${field('order_date','日期','date')}${field('start_time','开始','time')}${field('end_time','结束','time')}</div><div class="split">${field('pickup_location','起点')}${field('dropoff_location','终点')}</div><div class="triple">${field('order_type','订单类型')}${field('vehicle_type','车型')}${field('passenger_count','人数','number')}</div><div class="split">${field('agency_name','旅行社')}${field('price','价格','number')}</div>${field('remark','备注')}<div class="btns"><button onclick="saveSelected()">保存修改</button><button onclick="confirmAndAssign()">一键生成订单并派单</button><button class="secondary" onclick="assignExisting()">仅派当前订单</button></div>`;
}
function collect(){const d={};['order_date','start_time','end_time','pickup_location','dropoff_location','order_type','vehicle_type','passenger_count','agency_name','price','remark'].forEach(k=>d[k]=$('f_'+k)?.value||'');return d}
async function saveSelected(){if(!state.selected)return;const d=collect();if(state.selected.kind==='draft')await api(`/api/parser/drafts/${state.selected.id}`,{method:'PUT',body:JSON.stringify(d)});else await api(`/api/orders/${state.selected.id}`,{method:'PUT',body:JSON.stringify(d)});toast('已保存');await loadAll()}
async function confirmAndAssign(){if(!state.selected)return toast('先选订单');if(!state.driver||!state.vehicle)return toast('先选司机和车辆');await saveSelected();let orderId=state.selected.id;if(state.selected.kind==='draft'){const r=await api(`/api/parser/drafts/${state.selected.id}/confirm`,{method:'POST'});orderId=r.order_id}await api('/api/dispatch/assign',{method:'POST',body:JSON.stringify({order_ids:[orderId],driver_id:state.driver.id,vehicle_id:state.vehicle.id})});toast('已生成订单并派车');state.selected=null;await loadAll()}
async function assignExisting(){if(!state.selected||state.selected.kind!=='order')return toast('请选择待派订单');if(!state.driver||!state.vehicle)return toast('先选司机和车辆');await api('/api/dispatch/assign',{method:'POST',body:JSON.stringify({order_ids:[state.selected.id],driver_id:state.driver.id,vehicle_id:state.vehicle.id})});toast('已派车');state.selected=null;await loadAll()}
async function parseBatch(){const lines=$('batchText').value.split(/\\n+/).map(x=>x.trim()).filter(Boolean);if(!lines.length)return toast('先粘贴订单文本');for(const text of lines){await api('/api/parser/text',{method:'POST',body:JSON.stringify({text})})}$('batchText').value='';toast(`已解析 ${lines.length} 条草稿`);await loadAll()}
function renderResources(){ $('drivers').innerHTML=state.drivers.map(x=>`<div class="resource ${state.driver?.id===x.id?'active':''}" onclick="state.driver=${JSON.stringify(x).replaceAll('"','&quot;')};renderResources()"><b>${x.name}</b><small>${x.phone||''} · ${x.status}</small></div>`).join('')||'<div class="empty">无可用司机</div>'; $('vehicles').innerHTML=state.vehicles.map(x=>`<div class="resource ${state.vehicle?.id===x.id?'active':''}" onclick="state.vehicle=${JSON.stringify(x).replaceAll('"','&quot;')};renderResources()"><b>${x.plate_number}</b><small>${x.vehicle_type||''} · ${x.seat_count||''}座</small></div>`).join('')||'<div class="empty">无可用车辆</div>'}
function renderAssigned(){ $('assignedRows').innerHTML=state.assignments.map(x=>`<tr><td>${timeText(x)}</td><td><b>${x.pickup_location||'-'}</b><small>${x.dropoff_location||'-'}</small></td><td>${x.driver_name||'-'}</td><td>${x.plate_number||'-'}<small>${x.vehicle_type||''}</small></td><td><span class="tag">${x.execution_status||x.status}</span></td></tr>`).join('')||'<tr><td colspan="5" class="empty">暂无已派订单</td></tr>'}
function renderCalendar(){ $('calendarItems').innerHTML=state.calendar.map(x=>`<div class="event" style="border-left-color:${x.calendar_color||'#2f80ed'}"><div><b>${x.plate_number||'-'}</b><span>${x.start_time||''}-${x.end_time||''}</span></div><p>${route(x)}</p><small>${x.driver_name||'-'} · ${x.dispatch_status||'-'}</small></div>`).join('')||'<div class="empty">暂无日历派车</div>'}
loadAll().catch(e=>{console.error(e);$('status').textContent='API 加载失败';toast(e.message)})
</script>
</body>
</html>"""
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_dashboard_page(self) -> None:
        html = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>调度运营驾驶舱</title>
  <style>
    *{box-sizing:border-box}body{margin:0;font-family:Arial,'Microsoft YaHei',sans-serif;background:#eef2f6;color:#17202a}.layout{display:flex;min-height:100vh}.side{width:210px;background:#172433;color:#fff;padding:24px 18px;position:sticky;top:0;height:100vh}.brand{font-size:22px;font-weight:800;line-height:1.35;margin-bottom:28px}.nav a{display:block;color:#d8e2ee;text-decoration:none;padding:11px 12px;border-radius:6px;margin:4px 0;font-size:15px}.nav a.active{background:#27415d;color:#fff}main{flex:1;padding:22px 26px 44px}.top{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:16px}h1{margin:0;font-size:30px}.sub{color:#667085;margin-top:6px}.pill{background:#fff;border:1px solid #d8e0ea;border-radius:18px;padding:8px 12px;color:#344054;font-size:13px}.kpis{display:grid;grid-template-columns:repeat(6,minmax(128px,1fr));gap:11px;margin-bottom:14px}.kpi{background:#fff;border:1px solid #d8e0ea;border-radius:8px;padding:13px 14px;border-top:4px solid #98a2b3}.kpi.blue{border-top-color:#2f80ed}.kpi.green{border-top-color:#219653}.kpi.orange{border-top-color:#f2994a}.kpi.red{border-top-color:#eb5757}.kpi.purple{border-top-color:#7b61ff}.kpi span{color:#667085;font-size:13px}.kpi b{display:block;font-size:28px;margin-top:5px}.board{display:grid;grid-template-columns:1.15fr .85fr;gap:14px;align-items:start}.panel{background:#fff;border:1px solid #d8e0ea;border-radius:8px;padding:15px;margin-bottom:14px;box-shadow:0 1px 2px rgba(16,24,40,.04)}.panel h2{font-size:18px;margin:0 0 12px;display:flex;justify-content:space-between;align-items:center}.panel h2 small{font-size:12px;color:#667085;font-weight:400}.matrix{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}.cell{border:1px solid #e3e9f1;border-radius:8px;background:#fbfcfe;padding:12px;min-height:82px}.cell strong{display:block;font-size:24px;margin:5px 0}.cell span,.muted{color:#667085;font-size:13px}.bars{display:grid;gap:10px}.bar-row{display:grid;grid-template-columns:92px 1fr 42px;gap:9px;align-items:center}.bar{height:12px;background:#eef3f8;border-radius:8px;overflow:hidden}.bar i{display:block;height:100%;background:#2f80ed;border-radius:8px}.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px}.card{border:1px solid #e3e9f1;background:#fbfcfe;border-radius:8px;padding:12px}.card b{display:block;margin-bottom:6px}.card small{color:#667085;line-height:1.5}.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}button{border:0;border-radius:6px;padding:8px 12px;font-weight:700;cursor:pointer;background:#1f6feb;color:#fff}button.secondary{background:#eef3f8;color:#344054;border:1px solid #cbd5e1}textarea,input{width:100%;border:1px solid #cbd5e1;border-radius:6px;padding:9px 10px;font-size:14px}textarea{min-height:92px;resize:vertical}.details{display:none;margin-top:12px;border-top:1px solid #e6ebf1;padding-top:10px}table{width:100%;border-collapse:collapse}th{text-align:left;color:#667085;font-size:12px;border-bottom:1px solid #e6ebf1;padding:8px}td{border-bottom:1px solid #edf1f5;padding:9px 8px;vertical-align:top;font-size:14px}td small{display:block;color:#667085;margin-top:3px}.tag{display:inline-block;background:#eef3f8;border:1px solid #d8e0ea;border-radius:13px;padding:3px 8px;color:#344054;font-size:12px}.empty{padding:18px;text-align:center;color:#98a2b3}.toast{position:fixed;right:24px;bottom:24px;background:#172433;color:#fff;border-radius:8px;padding:12px 14px;display:none}@media(max-width:1100px){.side{width:92px;padding:20px 10px}.brand{text-align:center;font-size:18px}.nav a{text-align:center;font-size:13px}.board,.kpis,.matrix{grid-template-columns:1fr}main{padding:18px}}
  </style>
</head>
<body>
<div class="layout">
  <aside class="side"><div class="brand">调度<br>驾驶舱</div><nav class="nav"><a class="active" href="#overview">总览</a><a href="#input">录单</a><a href="#dispatch">派车</a><a href="#calendar">日历</a><a href="#details">明细</a></nav></aside>
  <main>
    <section class="top" id="overview"><div><h1>运营驾驶舱</h1><div class="sub">先看 KPI 和多维分布，需要具体数据时再展开明细表</div></div><div class="pill" id="status">加载中</div></section>
    <section class="kpis" id="kpis"></section>
    <section class="board">
      <div>
        <div class="panel"><h2>今日订单状态矩阵 <small>从录入到执行</small></h2><div class="matrix" id="statusMatrix"></div><div class="toolbar"><button class="secondary" onclick="toggle('orderDetail')">展开订单明细</button></div><div class="details" id="orderDetail"><table><thead><tr><th>时间</th><th>路线</th><th>类型/车型</th><th>旅行社</th><th>状态</th></tr></thead><tbody id="orderRows"></tbody></table></div></div>
        <div class="panel" id="dispatch"><h2>派车负载 <small>司机 / 车辆 / 未报备</small></h2><div class="bars" id="loadBars"></div><div class="toolbar"><button class="secondary" onclick="toggle('dispatchDetail')">展开派车明细</button></div><div class="details" id="dispatchDetail"><table><thead><tr><th>时间</th><th>路线</th><th>司机</th><th>车辆</th><th>执行</th></tr></thead><tbody id="dispatchRows"></tbody></table></div></div>
        <div class="panel" id="calendar"><h2>日历摘要 <small>今天车辆排班卡片</small></h2><div class="cards" id="calendarCards"></div></div>
      </div>
      <div>
        <div class="panel" id="input"><h2>快速批量录单 <small>粘贴后生成草稿</small></h2><textarea id="batchText" placeholder="一行一单，例如：5/24 14:10 关西接机大阪 10座600"></textarea><div class="toolbar"><button onclick="parseBatch()">批量解析</button><button class="secondary" onclick="loadAll()">刷新</button></div></div>
        <div class="panel"><h2>待处理池 <small>需要调度员动作</small></h2><div class="cards" id="actionCards"></div></div>
        <div class="panel"><h2>草稿预览 <small>点击展开看完整草稿表</small></h2><div class="matrix" id="draftMatrix"></div><div class="toolbar"><button class="secondary" onclick="toggle('draftDetail')">展开草稿明细</button></div><div class="details" id="draftDetail"><table><thead><tr><th>原文</th><th>时间</th><th>路线</th><th>状态</th></tr></thead><tbody id="draftRows"></tbody></table></div></div>
      </div>
    </section>
  </main>
</div>
<div class="toast" id="toast"></div>
<script>
const $=id=>document.getElementById(id);let data={};
function toast(msg){const el=$('toast');el.textContent=msg;el.style.display='block';setTimeout(()=>el.style.display='none',2400)}
function toggle(id){const el=$(id);el.style.display=el.style.display==='block'?'none':'block'}
async function api(path,opts={}){const res=await fetch(path,{headers:{'Content-Type':'application/json'},...opts});const body=await res.json();if(!res.ok)throw new Error(body.error||res.statusText);return body}
function route(x){return `${x.pickup_location||'-'} -> ${x.dropoff_location||'-'}`}function timeText(x){return `${x.order_date||'-'} ${x.start_time||''}${x.end_time?'-'+x.end_time:''}`}
function cell(label,value,sub=''){return `<div class="cell"><span>${label}</span><strong>${value||0}</strong><span>${sub}</span></div>`}
async function loadAll(){
  const [summary,orders,unassigned,assignments,drivers,vehicles,drafts,cal]=await Promise.all([api('/api/dashboard/summary'),api('/api/orders'),api('/api/dispatch/unassigned-orders'),api('/api/dispatch/assignments'),api('/api/dispatch/drivers'),api('/api/dispatch/vehicles'),api('/api/parser/drafts'),api('/api/calendar/dispatch?view=day')]);
  data={summary,orders:orders.orders||[],unassigned:unassigned.orders||[],assignments:assignments.assignments||[],drivers:drivers.drivers||[],vehicles:vehicles.vehicles||[],drafts:drafts.drafts||[],calendar:cal.items||[]};
  render();
}
function render(){
  const s=data.summary||{};$('status').textContent=`${s.date||''} · API 已连接`;
  const k=[['今日订单',s.today_orders,'blue'],['已派车',s.today_assigned_orders,'green'],['未派车',s.today_unassigned_orders,'red'],['执行中',s.today_in_service_orders,'purple'],['已完成',s.today_completed_orders,'green'],['待确认草稿',s.pending_drafts,'orange']];
  $('kpis').innerHTML=k.map(x=>`<div class="kpi ${x[2]}"><span>${x[0]}</span><b>${x[1]||0}</b></div>`).join('');
  $('statusMatrix').innerHTML=cell('待解析/待确认草稿',s.pending_drafts,'复制订单后先处理')+cell('未派车订单',s.today_unassigned_orders,'需要安排司机车辆')+cell('已派车订单',s.today_assigned_orders,'已进入日历')+cell('未报备订单',s.unreported_assignments,'司机端还没回传')+cell('已确认',s.today_confirmed_orders,'司机已接单')+cell('已出库',s.today_departed_orders,'车辆已出发')+cell('已到达',s.today_arrived_orders,'到达上车点')+cell('已完成/归库',(s.today_completed_orders||0)+' / '+(s.today_returned_orders||0),'执行闭环');
  $('actionCards').innerHTML=[`<div class="card"><b>${s.pending_drafts||0} 条草稿待确认</b><small>先批量解析，再人工修正字段。</small></div>`,`<div class="card"><b>${s.today_unassigned_orders||0} 单未派车</b><small>进入录单派车页选择司机和车辆。</small></div>`,`<div class="card"><b>${s.missing_price_orders||0} 单价格缺失</b><small>结算前需要补价格。</small></div>`,`<div class="card"><b>${s.unreported_assignments||0} 单未报备</b><small>需要提醒司机端更新状态。</small></div>`].join('');
  const max=Math.max(1,data.assignments.length);const driverNames=[...new Set(data.assignments.map(x=>x.driver_name||'-'))].slice(0,8);$('loadBars').innerHTML=driverNames.map(name=>{const n=data.assignments.filter(x=>(x.driver_name||'-')===name).length;return `<div class="bar-row"><span class="muted">${name}</span><div class="bar"><i style="width:${Math.max(8,n/max*100)}%"></i></div><b>${n}</b></div>`}).join('')||'<div class="empty">暂无派车负载</div>';
  $('draftMatrix').innerHTML=cell('parsed',data.drafts.filter(x=>x.parse_status==='parsed').length,'已解析待确认')+cell('pending',data.drafts.filter(x=>x.parse_status==='pending').length,'等待处理')+cell('confirmed',data.drafts.filter(x=>x.parse_status==='confirmed').length,'已入库')+cell('failed',data.drafts.filter(x=>x.parse_status==='failed').length,'原文保留');
  $('calendarCards').innerHTML=data.calendar.slice(0,12).map(x=>`<div class="card" style="border-left:5px solid ${x.calendar_color||'#2f80ed'}"><b>${x.plate_number||'-'} · ${x.start_time||''}-${x.end_time||''}</b><small>${route(x)}<br>${x.driver_name||'-'} · ${x.dispatch_status||'-'}</small></div>`).join('')||'<div class="empty">今日日历暂无派车</div>';
  $('orderRows').innerHTML=data.orders.slice(0,20).map(x=>`<tr><td>${timeText(x)}</td><td><b>${route(x)}</b></td><td>${x.order_type||'-'}<small>${x.vehicle_type||''}</small></td><td>${x.agency_name||'-'}</td><td><span class="tag">${x.dispatch_status||'-'}</span></td></tr>`).join('')||'<tr><td colspan="5" class="empty">暂无订单</td></tr>';
  $('dispatchRows').innerHTML=data.assignments.slice(0,20).map(x=>`<tr><td>${timeText(x)}</td><td><b>${route(x)}</b></td><td>${x.driver_name||'-'}</td><td>${x.plate_number||'-'}</td><td><span class="tag">${x.execution_status||x.status||'-'}</span></td></tr>`).join('')||'<tr><td colspan="5" class="empty">暂无派车</td></tr>';
  $('draftRows').innerHTML=data.drafts.slice(0,20).map(x=>`<tr><td>${x.raw_text||'-'}</td><td>${timeText(x)}</td><td>${route(x)}</td><td><span class="tag">${x.parse_status||'-'}</span></td></tr>`).join('')||'<tr><td colspan="4" class="empty">暂无草稿</td></tr>';
}
async function parseBatch(){const lines=$('batchText').value.split(/\\n+/).map(x=>x.trim()).filter(Boolean);if(!lines.length)return toast('先粘贴订单文本');for(const text of lines){await api('/api/parser/text',{method:'POST',body:JSON.stringify({text})})}$('batchText').value='';toast(`已解析 ${lines.length} 条草稿`);await loadAll()}
loadAll().catch(e=>{console.error(e);$('status').textContent='API 加载失败';toast(e.message)})
</script>
</body>
</html>"""
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_dashboard_page(self) -> None:
        html = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>调度派单台</title>
  <style>
    *{box-sizing:border-box}body{margin:0;font-family:Arial,'Microsoft YaHei',sans-serif;background:#eef2f6;color:#17202a}.layout{display:flex;min-height:100vh}.side{width:206px;background:#172433;color:#fff;padding:24px 18px;position:sticky;top:0;height:100vh}.brand{font-size:22px;font-weight:800;line-height:1.35;margin-bottom:28px}.nav a{display:block;color:#d8e2ee;text-decoration:none;padding:11px 12px;border-radius:6px;margin:4px 0;font-size:15px}.nav a.active{background:#27415d;color:#fff}main{flex:1;padding:22px 26px 44px}.top{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:14px}h1{margin:0;font-size:30px}.sub{color:#667085;margin-top:6px}.pill{background:#fff;border:1px solid #d8e0ea;border-radius:18px;padding:8px 12px;color:#344054;font-size:13px}.kpis{display:grid;grid-template-columns:repeat(5,minmax(130px,1fr));gap:10px;margin-bottom:14px}.kpi{background:#fff;border:1px solid #d8e0ea;border-radius:8px;padding:12px;border-top:4px solid #2f80ed}.kpi b{display:block;font-size:28px;margin-top:4px}.kpi span{color:#667085;font-size:13px}.panel{background:#fff;border:1px solid #d8e0ea;border-radius:8px;padding:15px;margin-bottom:14px;box-shadow:0 1px 2px rgba(16,24,40,.04)}.panel h2{font-size:18px;margin:0 0 12px;display:flex;justify-content:space-between;align-items:center}.panel h2 small{font-size:12px;color:#667085;font-weight:400}textarea,input,select{width:100%;border:1px solid #cbd5e1;border-radius:6px;padding:8px 9px;font-size:13px;background:#fff}textarea{min-height:105px;resize:vertical}.toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:10px}button{border:0;border-radius:6px;padding:8px 12px;font-weight:700;cursor:pointer;background:#1f6feb;color:#fff}button.secondary{background:#eef3f8;color:#344054;border:1px solid #cbd5e1}button.assign{background:#219653}.hint{color:#667085;font-size:13px}.flow{display:grid;grid-template-columns:1fr 1fr;gap:12px}.table-wrap{overflow:auto;max-height:520px;border:1px solid #e6ebf1;border-radius:8px}table{width:100%;border-collapse:separate;border-spacing:0;min-width:1180px}th{text-align:left;color:#667085;font-size:12px;background:#f8fafc;border-bottom:1px solid #e6ebf1;padding:8px;position:sticky;top:0;z-index:1}td{border-bottom:1px solid #edf1f5;padding:8px;vertical-align:top;font-size:13px}td.route{min-width:220px}td.compact{min-width:88px}td.medium{min-width:130px}.tag{display:inline-block;background:#eef3f8;border:1px solid #d8e0ea;border-radius:13px;padding:3px 8px;color:#344054;font-size:12px}.empty{padding:24px;text-align:center;color:#98a2b3}.card{border:1px solid #e3e9f1;background:#fbfcfe;border-radius:8px;padding:12px}.toast{position:fixed;right:24px;bottom:24px;background:#172433;color:#fff;border-radius:8px;padding:12px 14px;display:none;box-shadow:0 8px 24px rgba(16,24,40,.2)}@media(max-width:1100px){.side{width:92px;padding:20px 10px}.brand{text-align:center;font-size:18px}.nav a{text-align:center;font-size:13px}.flow,.kpis{grid-template-columns:1fr}main{padding:18px}}
  </style>
</head>
<body>
<div class="layout">
  <aside class="side"><div class="brand">调度<br>派单台</div><nav class="nav"><a class="active" href="#parse">解析录单</a><a href="#pending">待派订单</a><a href="#assigned">已派订单</a></nav></aside>
  <main>
    <section class="top"><div><h1>解析订单 -> 修正 -> 一键派单</h1><div class="sub">上表越派越少，下表越派越多；派单写入 assignments 后司机端即可看到自己的订单。</div></div><div class="pill" id="status">加载中</div></section>
    <section class="kpis" id="kpis"></section>
    <section class="panel" id="parse">
      <h2>1. 批量解析订单 <small>一行一单，先保留原文生成草稿</small></h2>
      <textarea id="batchText" placeholder="5/24 14:10 关西接机大阪 10座600
5月7日 关西机场送大阪市内 6人 丰田海狮
羽田接机 15:30 银座 2位客人"></textarea>
      <div class="toolbar"><button onclick="parseBatch()">批量解析订单</button><button class="secondary" onclick="loadAll()">刷新</button><span class="hint">解析结果会进入下面的“待派订单”，可以直接改字段并派单。</span></div>
    </section>
    <section class="panel" id="pending">
      <h2>2. 待派订单 <small>直接在表格里修正字段，选择司机和车辆后派单</small></h2>
      <div class="table-wrap"><table><thead><tr><th>来源</th><th>订单号</th><th>开始日期</th><th>开始时间</th><th>结束日期</th><th>结束时间</th><th>路线</th><th>类型</th><th>车型</th><th>人数</th><th>旅行社</th><th>价格</th><th>司机</th><th>车辆</th><th>操作</th></tr></thead><tbody id="pendingRows"></tbody></table></div>
    </section>
    <section class="flow">
      <div class="panel" id="assigned"><h2>3. 已安排司机车辆的订单 <small>派完后进入这里</small></h2><div class="table-wrap"><table><thead><tr><th>订单号</th><th>开始</th><th>结束</th><th>路线</th><th>价格</th><th>司机</th><th>车辆</th><th>执行状态</th><th>司机端</th></tr></thead><tbody id="assignedRows"></tbody></table></div></div>
      <div class="panel"><h2>4. 日历同步结果 <small>来自 active assignments</small></h2><div id="calendarCards"></div></div>
    </section>
  </main>
</div>
<div class="toast" id="toast"></div>
<script>
const $=id=>document.getElementById(id);let state={drafts:[],orders:[],drivers:[],vehicles:[],assignments:[],calendar:[],summary:{}};
function toast(msg){const el=$('toast');el.textContent=msg;el.style.display='block';setTimeout(()=>el.style.display='none',2600)}
async function api(path,opts={}){const res=await fetch(path,{headers:{'Content-Type':'application/json'},...opts});const body=await res.json();if(!res.ok)throw new Error(body.error||res.statusText);return body}
function route(x){return `${x.pickup_location||''} -> ${x.dropoff_location||''}`}function timeText(x){return `${x.order_date||'-'} ${x.start_time||''}${x.end_time?'-'+x.end_time:''}`}function esc(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
async function loadAll(){
  const [summary,drafts,orders,drivers,vehicles,assignments,cal]=await Promise.all([api('/api/dashboard/summary'),api('/api/parser/drafts'),api('/api/dispatch/unassigned-orders'),api('/api/dispatch/drivers'),api('/api/dispatch/vehicles'),api('/api/dispatch/assignments'),api('/api/calendar/dispatch?view=day')]);
  state.summary=summary;state.drafts=(drafts.drafts||[]).filter(x=>x.parse_status!=='confirmed'&&x.parse_status!=='discarded');state.orders=orders.orders||[];state.drivers=drivers.drivers||[];state.vehicles=vehicles.vehicles||[];state.assignments=assignments.assignments||[];state.calendar=cal.items||[];render();
}
function render(){
  const s=state.summary;$('status').textContent=`${s.date||''} · API 已连接`;
  $('kpis').innerHTML=[['待确认草稿',state.drafts.length],['待派订单',state.orders.length],['已派订单',state.assignments.length],['可用司机',state.drivers.length],['可用车辆',state.vehicles.length]].map(x=>`<div class="kpi"><span>${x[0]}</span><b>${x[1]||0}</b></div>`).join('');
  renderPending();renderAssigned();renderCalendar();
}
function driverOptions(){return `<option value="">选司机</option>`+state.drivers.map(d=>`<option value="${d.id}">${esc(d.name)} ${esc(d.phone||'')}</option>`).join('')}
function vehicleOptions(){return `<option value="">选车辆</option>`+state.vehicles.map(v=>`<option value="${v.id}">${esc(v.plate_number)} ${esc(v.vehicle_type||'')}</option>`).join('')}
function input(row,key,type='text'){return `<input data-key="${key}" type="${type}" value="${esc(row[key])}">`}
function renderPending(){
  const rows=[...state.drafts.map(x=>({kind:'draft',...x})),...state.orders.map(x=>({kind:'order',...x}))];
  $('pendingRows').innerHTML=rows.map(r=>`<tr data-kind="${r.kind}" data-id="${r.id}"><td><span class="tag">${r.kind==='draft'?'解析草稿':'待派订单'}</span><small>${esc(r.raw_text||'')}</small></td><td class="medium">${input(r,'oid')}</td><td class="compact">${input(r,'order_date','date')}</td><td class="compact">${input(r,'start_time','time')}</td><td class="compact">${input(r,'end_date','date')}</td><td class="compact">${input(r,'end_time','time')}</td><td class="route">${input(r,'pickup_location')}<br>${input(r,'dropoff_location')}</td><td class="medium">${input(r,'order_type')}</td><td class="medium">${input(r,'vehicle_type')}</td><td class="compact">${input(r,'passenger_count','number')}</td><td class="medium">${input(r,'agency_name')}</td><td class="compact">${input(r,'price','number')}</td><td class="medium"><select data-role="driver">${driverOptions()}</select></td><td class="medium"><select data-role="vehicle">${vehicleOptions()}</select></td><td><button class="assign" onclick="assignRow(this)">一键派单</button></td></tr>`).join('')||'<tr><td colspan="15" class="empty">待派订单已清空</td></tr>';
}
function rowPayload(tr){const data={};tr.querySelectorAll('input[data-key]').forEach(i=>data[i.dataset.key]=i.value);return data}
async function assignRow(btn){
  const tr=btn.closest('tr');const kind=tr.dataset.kind;const id=tr.dataset.id;const driverId=tr.querySelector('[data-role=driver]').value;const vehicleId=tr.querySelector('[data-role=vehicle]').value;if(!driverId||!vehicleId)return toast('请先选择司机和车辆');
  btn.disabled=true;btn.textContent='派单中';
  try{
    const payload=rowPayload(tr);let orderId=id;
    if(kind==='draft'){await api(`/api/parser/drafts/${id}`,{method:'PUT',body:JSON.stringify(payload)});const confirmed=await api(`/api/parser/drafts/${id}/confirm`,{method:'POST'});orderId=confirmed.order_id}else{await api(`/api/orders/${id}`,{method:'PUT',body:JSON.stringify(payload)})}
    await api('/api/dispatch/assign',{method:'POST',body:JSON.stringify({order_ids:[Number(orderId)],driver_id:Number(driverId),vehicle_id:Number(vehicleId)})});
    toast('派单成功，司机端已可见');await loadAll();
  }catch(e){toast(e.message);btn.disabled=false;btn.textContent='一键派单'}
}
function renderAssigned(){
  $('assignedRows').innerHTML=state.assignments.map(x=>`<tr><td><b>${esc(x.oid||'-')}</b></td><td>${esc(x.order_date||'-')}<small>${esc(x.start_time||'')}</small></td><td>${esc(x.end_date||x.order_date||'-')}<small>${esc(x.end_time||'')}</small></td><td><b>${esc(x.pickup_location||'-')}</b><small>${esc(x.dropoff_location||'-')}</small></td><td>${esc(x.price??'-')}</td><td>${esc(x.driver_name||'-')}</td><td>${esc(x.plate_number||'-')}<small>${esc(x.assigned_vehicle_type||x.vehicle_type||'')}</small></td><td><span class="tag">${esc(x.execution_status||x.status||'-')}</span></td><td><span class="tag">driver_id=${esc(x.driver_id)}</span></td></tr>`).join('')||'<tr><td colspan="9" class="empty">暂无已派订单</td></tr>';
}
function renderCalendar(){
  $('calendarCards').innerHTML=state.calendar.slice(0,12).map(x=>`<div class="card" style="border-left:5px solid ${esc(x.calendar_color||'#2f80ed')};margin-bottom:8px"><b>${esc(x.plate_number||'-')} · ${esc(x.start_time||'')}-${esc(x.end_time||'')}</b><small>${esc(route(x))}<br>${esc(x.driver_name||'-')} · ${esc(x.dispatch_status||'-')}</small></div>`).join('')||'<div class="empty">暂无日历派车</div>';
}
async function parseBatch(){const lines=$('batchText').value.split(/\\n+/).map(x=>x.trim()).filter(Boolean);if(!lines.length)return toast('先粘贴订单文本');for(const text of lines){await api('/api/parser/text',{method:'POST',body:JSON.stringify({text})})}$('batchText').value='';toast(`已解析 ${lines.length} 条`);await loadAll()}
loadAll().catch(e=>{console.error(e);$('status').textContent='API 加载失败';toast(e.message)})
</script>
</body>
</html>"""
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_dashboard_page(self) -> None:
        html = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>调度派单日历</title>
  <style>
    *{box-sizing:border-box}body{margin:0;font-family:Arial,'Microsoft YaHei',sans-serif;background:#f3f6fa;color:#17202a}.layout{display:flex;min-height:100vh}.side{width:206px;background:#172433;color:#fff;padding:24px 18px;position:sticky;top:0;height:100vh}.brand{font-size:22px;font-weight:800;line-height:1.35;margin-bottom:28px}.nav a{display:block;color:#d8e2ee;text-decoration:none;padding:11px 12px;border-radius:6px;margin:4px 0;font-size:15px}.nav a.active{background:#27415d;color:#fff}main{flex:1;padding:22px 26px 44px}.top{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:14px}h1{margin:0;font-size:30px}.sub{color:#667085;margin-top:6px}.pill{background:#fff;border:1px solid #d8e0ea;border-radius:18px;padding:8px 12px;color:#344054;font-size:13px}.panel{background:#fff;border:1px solid #d8e0ea;border-radius:8px;padding:15px;margin-bottom:14px;box-shadow:0 1px 2px rgba(16,24,40,.04)}.panel h2{font-size:18px;margin:0 0 12px;display:flex;justify-content:space-between;align-items:center}.panel h2 small{font-size:12px;color:#667085;font-weight:400}.toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.tabs{display:flex;border:1px solid #d8e0ea;border-radius:7px;overflow:hidden}.tabs button{border:0;border-right:1px solid #d8e0ea;background:#fff;color:#344054;border-radius:0}.tabs button.active{background:#2563eb;color:#fff}button{border:0;border-radius:6px;padding:8px 12px;font-weight:700;cursor:pointer;background:#1f6feb;color:#fff}button.secondary{background:#eef3f8;color:#344054;border:1px solid #cbd5e1}button.assign{background:#219653}input,select,textarea{border:1px solid #cbd5e1;border-radius:6px;padding:8px 9px;font-size:13px;background:#fff}textarea{width:100%;min-height:88px;resize:vertical}.kpis{display:grid;grid-template-columns:repeat(6,minmax(120px,1fr));gap:10px;margin:12px 0}.kpi{background:#fff;border:1px solid #d8e0ea;border-radius:8px;padding:11px;border-top:4px solid #98a2b3;cursor:pointer}.kpi.active{outline:2px solid #172433}.kpi b{display:block;font-size:25px;margin-top:4px}.kpi span{color:#667085;font-size:13px}.orange{border-top-color:#f59e0b}.blue{border-top-color:#2563eb}.green{border-top-color:#16a34a}.red{border-top-color:#ef4444}.purple{border-top-color:#8b5cf6}.gray{border-top-color:#6b7280}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}.table-wrap{overflow:auto;max-height:420px;border:1px solid #e6ebf1;border-radius:8px}table{width:100%;border-collapse:separate;border-spacing:0;min-width:1180px}th{text-align:left;color:#667085;font-size:12px;background:#f8fafc;border-bottom:1px solid #e6ebf1;padding:8px;position:sticky;top:0;z-index:2}td{border-bottom:1px solid #edf1f5;padding:8px;vertical-align:top;font-size:13px}.tag{display:inline-block;background:#eef3f8;border:1px solid #d8e0ea;border-radius:13px;padding:3px 8px;color:#344054;font-size:12px}.empty{padding:24px;text-align:center;color:#98a2b3}.hint{color:#667085;font-size:13px}.calendar-shell{overflow:auto;border:1px solid #d8e0ea;border-radius:8px;background:#fff}.calendar-shell.full{position:fixed;z-index:20;inset:14px;background:#fff;padding:14px}.time-head,.vehicle-row{display:grid;min-width:1240px}.time-head{position:sticky;top:0;z-index:3;background:#fff;border-bottom:1px solid #e5eaf1}.head-cell{padding:10px 8px;border-right:1px solid #edf1f5;text-align:center;color:#526071;font-size:13px}.vehicle-name{position:sticky;left:0;z-index:2;background:#fbfcfe;border-right:1px solid #e5eaf1;padding:12px;font-weight:800}.vehicle-name small{display:block;color:#667085;font-weight:400;margin-top:4px}.vehicle-row{position:relative;border-bottom:1px solid #edf1f5;min-height:86px}.slot{border-right:1px solid #edf1f5;min-height:86px;background:linear-gradient(#fff,#fff)}.eventbar{position:absolute;border:1px solid;border-radius:6px;padding:6px 8px;min-height:42px;overflow:hidden;font-size:12px;box-shadow:0 1px 2px rgba(16,24,40,.06);white-space:nowrap}.eventbar b{display:block;font-size:13px;margin-bottom:2px}.eventbar small{color:#344054}.c-unassigned{background:#fff7ed;border-color:#f59e0b;color:#92400e}.c-assigned{background:#eff6ff;border-color:#60a5fa;color:#1d4ed8}.c-completed{background:#ecfdf3;border-color:#34d399;color:#047857}.c-unsettled{background:#fff7ed;border-color:#fb923c;color:#c2410c}.c-settled{background:#f5f3ff;border-color:#a78bfa;color:#6d28d9}.c-default{background:#f8fafc;border-color:#94a3b8;color:#334155}.toast{position:fixed;right:24px;bottom:24px;background:#172433;color:#fff;border-radius:8px;padding:12px 14px;display:none}@media(max-width:1100px){.side{width:92px;padding:20px 10px}.brand{text-align:center;font-size:18px}.nav a{text-align:center;font-size:13px}.grid2,.kpis{grid-template-columns:1fr}main{padding:18px}}
  </style>
</head>
<body>
<div class="layout">
  <aside class="side"><div class="brand">调度<br>日历</div><nav class="nav"><a class="active" href="#calendar">车辆日历</a><a href="#parse">解析录单</a><a href="#pending">待派订单</a><a href="#assigned">已派订单</a></nav></aside>
  <main>
    <section class="top"><div><h1>车辆占用矩阵日历</h1><div class="sub">纵列是车辆，横排是 24h / 7d / 30d。跨日订单用连续横条表示：开始日 -> 中间日 -> 结束日。</div></div><div class="pill" id="status">加载中</div></section>
    <section class="panel" id="calendar">
      <h2>日历窗口 <small>优先显示已安排车辆的订单，可全屏</small></h2>
      <div class="toolbar">
        <div class="tabs"><button id="tab-day" onclick="setView('day')">24h</button><button id="tab-week" onclick="setView('week')">7d</button><button id="tab-month" onclick="setView('month')">30d</button></div>
        <input type="date" id="baseDate" onchange="loadAll()" />
        <select id="vehicleFilter" onchange="loadAll()"><option value="">全部车辆</option></select>
        <button class="secondary" onclick="toggleFull()">全屏日历</button>
        <span class="hint">每天 6-8 单时同一车辆行会自动堆叠多条占用，不互相覆盖。</span>
      </div>
      <div class="kpis" id="statusKpis"></div>
      <div class="calendar-shell" id="calendarShell"><div id="calendarGrid"></div></div>
    </section>
    <section class="panel" id="parse"><h2>解析订单 <small>下个月预约也可直接录入，选对应日期/周期即可显示</small></h2><textarea id="batchText" placeholder="一行一单，例如：3/22 09:00 大阪->京都 4人 50000"></textarea><div class="toolbar"><button onclick="parseBatch()">批量解析订单</button><button class="secondary" onclick="loadAll()">刷新</button></div></section>
    <section class="panel" id="pending"><h2>待派订单 <small>修正后选司机车辆一键派单</small></h2><div class="table-wrap"><table><thead><tr><th>来源</th><th>订单号</th><th>开始日期</th><th>开始时间</th><th>结束日期</th><th>结束时间</th><th>路线</th><th>价格</th><th>司机</th><th>车辆</th><th>操作</th></tr></thead><tbody id="pendingRows"></tbody></table></div></section>
    <section class="panel" id="assigned"><h2>已派订单 <small>司机端按 driver_id 同步接收</small></h2><div class="table-wrap"><table><thead><tr><th>订单号</th><th>开始</th><th>结束</th><th>路线</th><th>价格</th><th>司机</th><th>车辆</th><th>状态</th></tr></thead><tbody id="assignedRows"></tbody></table></div></section>
  </main>
</div>
<div class="toast" id="toast"></div>
<script>
const $=id=>document.getElementById(id);let state={view:'day',status:'all',summary:{},orders:[],drafts:[],drivers:[],vehicles:[],assignments:[],calendar:[]};
function today(){return new Date().toISOString().slice(0,10)}function toast(msg){const el=$('toast');el.textContent=msg;el.style.display='block';setTimeout(()=>el.style.display='none',2600)}
async function api(path,opts={}){const res=await fetch(path,{headers:{'Content-Type':'application/json'},...opts});const body=await res.json();if(!res.ok)throw new Error(body.error||res.statusText);return body}
function esc(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}function route(x){return `${x.pickup_location||'-'} -> ${x.dropoff_location||'-'}`}function dadd(d,n){const x=new Date(d+'T00:00:00');x.setDate(x.getDate()+n);return x.toISOString().slice(0,10)}function minutes(t){if(!t||!t.includes(':'))return null;const [h,m]=t.split(':').map(Number);return h*60+m}
function setView(v){state.view=v;['day','week','month'].forEach(x=>$('tab-'+x).classList.toggle('active',x===v));loadAll()}
function toggleFull(){$('calendarShell').classList.toggle('full')}
async function loadAll(){
  if(!$('baseDate').value)$('baseDate').value=today();
  const date=$('baseDate').value, vehicle=$('vehicleFilter').value;
  const calView=state.view==='month'?'month':state.view;
  const qs=`view=${calView}&date=${date}${vehicle?'&vehicle_id='+vehicle:''}`;
  const [summary,orders,drafts,drivers,vehicles,assignments,cal]=await Promise.all([api('/api/dashboard/summary'),api('/api/orders'),api('/api/parser/drafts'),api('/api/dispatch/drivers'),api('/api/dispatch/vehicles'),api('/api/dispatch/assignments'),api('/api/calendar/dispatch?'+qs)]);
  state.summary=summary;state.orders=orders.orders||[];state.drafts=(drafts.drafts||[]).filter(x=>x.parse_status!=='confirmed'&&x.parse_status!=='discarded');state.drivers=drivers.drivers||[];state.vehicles=vehicles.vehicles||[];state.assignments=assignments.assignments||[];state.calendar=cal.items||[];
  render();
}
function render(){renderVehicleOptions();renderKpis();renderCalendar();renderPending();renderAssigned();$('status').textContent=`${$('baseDate').value} · ${state.view==='day'?'24h':state.view==='week'?'7d':'30d'}`}
function renderVehicleOptions(){const current=$('vehicleFilter').value;$('vehicleFilter').innerHTML='<option value="">全部车辆</option>'+state.vehicles.map(v=>`<option value="${v.id}">${esc(v.plate_number)} ${esc(v.vehicle_type||'')}</option>`).join('');$('vehicleFilter').value=current}
function countStatus(key){if(key==='unassigned')return state.orders.filter(x=>x.dispatch_status==='unassigned').length;if(key==='assigned')return state.assignments.length;if(key==='completed')return state.orders.filter(x=>['completed','returned'].includes(x.execution_status)).length;if(key==='settled')return state.orders.filter(x=>['settled','paid'].includes(x.settlement_status)).length;if(key==='unsettled')return state.orders.filter(x=>!['settled','paid'].includes(x.settlement_status)).length;return state.orders.length}
function renderKpis(){const k=[['unassigned','未派车','orange'],['assigned','已派车','blue'],['completed','已完成','green'],['unsettled','未结账','red'],['settled','已结账','purple'],['all','全部','gray']];$('statusKpis').innerHTML=k.map(x=>`<div class="kpi ${x[2]} ${state.status===x[0]?'active':''}" onclick="state.status='${x[0]}';render()"><span>${x[1]}</span><b>${countStatus(x[0])}</b></div>`).join('')}
function itemVisible(x){if(state.status==='all')return true;if(state.status==='assigned')return x.dispatch_status==='assigned';if(state.status==='completed')return ['completed','returned'].includes(x.execution_status);if(state.status==='settled')return ['settled','paid'].includes(x.settlement_status);if(state.status==='unsettled')return !['settled','paid'].includes(x.settlement_status);return true}
function colorClass(x){if(['completed','returned'].includes(x.execution_status))return 'c-completed';if(['settled','paid'].includes(x.settlement_status))return 'c-settled';if(!['settled','paid'].includes(x.settlement_status))return 'c-unsettled';if(x.dispatch_status==='assigned')return 'c-assigned';return 'c-default'}
function renderCalendar(){const cols=state.view==='day'?24:(state.view==='week'?7:30);const dates=[...Array(cols)].map((_,i)=>dadd($('baseDate').value,i));const vehicles=state.vehicles.filter(v=>!$('vehicleFilter').value||String(v.id)===$('vehicleFilter').value);const gridCols=`180px repeat(${cols}, 1fr)`;let html=`<div class="time-head" style="grid-template-columns:${gridCols}"><div class="head-cell">车辆</div>`;html+=dates.map((d,i)=>`<div class="head-cell">${state.view==='day'?String(i).padStart(2,'0')+':00':d.slice(5)}</div>`).join('')+'</div>';
  for(const v of vehicles){const items=state.calendar.filter(x=>x.vehicle_id===v.id&&itemVisible(x));const lanes=[];html+=`<div class="vehicle-row" style="grid-template-columns:${gridCols};min-height:${Math.max(86,items.length*48+28)}px"><div class="vehicle-name">${esc(v.plate_number||'-')}<small>${esc(v.vehicle_type||'')} ${esc(v.seat_count||'')}座</small></div>`+dates.map(()=>'<div class="slot"></div>').join('');
    items.forEach(x=>{let left=180,width=80;let startLabel='';const sd=x.order_date,ed=x.end_date||x.order_date;if(state.view==='day'){const s=minutes(x.start_time)??0,e=minutes(x.end_time)??1440;left=180+(s/1440)*(1060);width=Math.max(70,((Math.max(e,s+60)-s)/1440)*1060);startLabel=`${x.start_time||''}-${x.end_time||''}`}else{const start=Math.max(0,dates.indexOf(sd));const endIndex=dates.indexOf(ed);const end=endIndex>=0?endIndex:cols-1;const safeStart=start<0?0:start;left=180+(safeStart/cols)*1060;width=Math.max(80,((end-safeStart+1)/cols)*1060);startLabel=sd===ed?sd:`${sd} -> ${ed}`}const lane=lanes.length;lanes.push(1);html+=`<div class="eventbar ${colorClass(x)}" style="left:${left}px;width:${width}px;top:${12+lane*48}px"><b>${esc(x.oid||'')} ${esc(startLabel)}</b><small>${esc(route(x))} · ${esc(x.driver_name||'-')} · ${esc(x.price??'-')}</small></div>`});
    html+='</div>'}
  $('calendarGrid').innerHTML=html}
function driverOptions(){return '<option value="">司机</option>'+state.drivers.map(d=>`<option value="${d.id}">${esc(d.name)}</option>`).join('')}function vehicleOptions(){return '<option value="">车辆</option>'+state.vehicles.map(v=>`<option value="${v.id}">${esc(v.plate_number)}</option>`).join('')}function input(r,k,t='text'){return `<input data-key="${k}" type="${t}" value="${esc(r[k])}">`}
function renderPending(){const rows=[...state.drafts.map(x=>({kind:'draft',...x})),...state.orders.filter(x=>x.dispatch_status==='unassigned').map(x=>({kind:'order',...x}))];$('pendingRows').innerHTML=rows.map(r=>`<tr data-kind="${r.kind}" data-id="${r.id}"><td><span class="tag">${r.kind==='draft'?'草稿':'未派'}</span></td><td>${input(r,'oid')}</td><td>${input(r,'order_date','date')}</td><td>${input(r,'start_time','time')}</td><td>${input(r,'end_date','date')}</td><td>${input(r,'end_time','time')}</td><td>${input(r,'pickup_location')}<br>${input(r,'dropoff_location')}</td><td>${input(r,'price','number')}</td><td><select data-role="driver">${driverOptions()}</select></td><td><select data-role="vehicle">${vehicleOptions()}</select></td><td><button class="assign" onclick="assignRow(this)">一键派单</button></td></tr>`).join('')||'<tr><td colspan="11" class="empty">待派订单已清空</td></tr>'}
function rowPayload(tr){const data={};tr.querySelectorAll('input[data-key]').forEach(i=>data[i.dataset.key]=i.value);return data}
async function assignRow(btn){const tr=btn.closest('tr'),kind=tr.dataset.kind,id=tr.dataset.id,driverId=tr.querySelector('[data-role=driver]').value,vehicleId=tr.querySelector('[data-role=vehicle]').value;if(!driverId||!vehicleId)return toast('请先选择司机和车辆');btn.disabled=true;btn.textContent='派单中';try{const payload=rowPayload(tr);let orderId=id;if(kind==='draft'){await api(`/api/parser/drafts/${id}`,{method:'PUT',body:JSON.stringify(payload)});const r=await api(`/api/parser/drafts/${id}/confirm`,{method:'POST'});orderId=r.order_id}else{await api(`/api/orders/${id}`,{method:'PUT',body:JSON.stringify(payload)})}const assigned=await api('/api/dispatch/assign',{method:'POST',body:JSON.stringify({order_ids:[Number(orderId)],driver_id:Number(driverId),vehicle_id:Number(vehicleId)})});if(assigned.success===false)throw new Error('时间冲突，未派单');toast('派单成功，司机端已可见');await loadAll()}catch(e){toast(e.message);btn.disabled=false;btn.textContent='一键派单'}}
function renderAssigned(){$('assignedRows').innerHTML=state.assignments.map(x=>`<tr><td><b>${esc(x.oid||'-')}</b></td><td>${esc(x.order_date||'-')}<small>${esc(x.start_time||'')}</small></td><td>${esc(x.end_date||x.order_date||'-')}<small>${esc(x.end_time||'')}</small></td><td><b>${esc(x.pickup_location||'-')}</b><small>${esc(x.dropoff_location||'-')}</small></td><td>${esc(x.price??'-')}</td><td>${esc(x.driver_name||'-')}</td><td>${esc(x.plate_number||'-')}</td><td><span class="tag">${esc(x.execution_status||x.status||'-')}</span></td></tr>`).join('')||'<tr><td colspan="8" class="empty">暂无已派订单</td></tr>'}
async function parseBatch(){const lines=$('batchText').value.split(/\\n+/).map(x=>x.trim()).filter(Boolean);if(!lines.length)return toast('先粘贴订单文本');for(const text of lines){await api('/api/parser/text',{method:'POST',body:JSON.stringify({text})})}$('batchText').value='';toast(`已解析 ${lines.length} 条`);await loadAll()}
$('baseDate').value=today();setView('day');
</script>
</body>
</html>"""
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_dashboard_page(self) -> None:
        html = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>调度派单台</title>
  <style>
    *{box-sizing:border-box}body{margin:0;font-family:Arial,'Microsoft YaHei',sans-serif;background:#f3f6fa;color:#17202a}.layout{display:flex;min-height:100vh}.side{width:206px;background:#172433;color:#fff;padding:24px 18px;position:sticky;top:0;height:100vh}.brand{font-size:22px;font-weight:800;line-height:1.35;margin-bottom:28px}.nav a{display:block;color:#d8e2ee;text-decoration:none;padding:11px 12px;border-radius:6px;margin:4px 0;font-size:15px}.nav a.active{background:#27415d;color:#fff}main{flex:1;padding:22px 26px 44px}.top{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:14px}h1{margin:0;font-size:30px}.sub{color:#667085;margin-top:6px}.pill{background:#fff;border:1px solid #d8e0ea;border-radius:18px;padding:8px 12px;color:#344054;font-size:13px}.panel{background:#fff;border:1px solid #d8e0ea;border-radius:8px;padding:15px;margin-bottom:14px;box-shadow:0 1px 2px rgba(16,24,40,.04)}.panel h2{font-size:18px;margin:0 0 12px;display:flex;justify-content:space-between;align-items:center}.panel h2 small{font-size:12px;color:#667085;font-weight:400}.toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap}button{border:0;border-radius:6px;padding:8px 12px;font-weight:700;cursor:pointer;background:#1f6feb;color:#fff}button.secondary{background:#eef3f8;color:#344054;border:1px solid #cbd5e1}button.assign{background:#219653}button.assign.big{width:100%;padding:12px;margin-top:10px;font-size:15px}input,select,textarea{border:1px solid #cbd5e1;border-radius:6px;padding:8px 9px;font-size:13px;background:#fff}textarea{width:100%;min-height:86px;resize:vertical}.hint{color:#667085;font-size:13px}.details{display:none}.dispatch-grid{display:grid;grid-template-columns:minmax(760px,1fr) 240px 260px;gap:12px;align-items:stretch}.dispatch-grid>.panel{height:610px;display:flex;flex-direction:column}.dispatch-grid .table-wrap,.dispatch-grid .list{flex:1;max-height:none}.table-wrap{overflow:auto;max-height:480px;border:1px solid #e6ebf1;border-radius:8px}table{width:100%;border-collapse:separate;border-spacing:0;min-width:1280px}th{text-align:left;color:#667085;font-size:12px;background:#f8fafc;border-bottom:1px solid #e6ebf1;padding:8px;position:sticky;top:0;z-index:2}td{border-bottom:1px solid #edf1f5;padding:7px;vertical-align:top;font-size:13px}.row-select{cursor:pointer}.row-select.active{background:#eef6ff}.seq-input{width:54px}.cell-input{width:100%;min-width:82px}.route-input{width:100%;min-width:150px;margin-bottom:4px}.remark-input{width:100%;min-width:220px;min-height:62px;resize:vertical}.tag{display:inline-block;background:#eef3f8;border:1px solid #d8e0ea;border-radius:13px;padding:3px 8px;color:#344054;font-size:12px}.empty{padding:24px;text-align:center;color:#98a2b3}.list{display:grid;gap:8px;max-height:480px;overflow:auto}.pick-card{border:1px solid #e1e7ef;border-radius:8px;padding:10px;background:#fbfcfe;cursor:pointer}.pick-card.active{border-color:#219653;background:#eefaf2;box-shadow:0 0 0 2px rgba(33,150,83,.12)}.pick-card b{display:block}.pick-card small{color:#667085}.selected-box{background:#f8fafc;border:1px solid #e1e7ef;border-radius:8px;padding:10px;margin-bottom:10px;color:#344054}.calendar-shell{overflow:auto;border:1px solid #d8e0ea;border-radius:8px;background:#fff}.time-head,.vehicle-row{display:grid;min-width:1240px}.time-head{position:sticky;top:0;z-index:3;background:#fff;border-bottom:1px solid #e5eaf1}.head-cell{padding:10px 8px;border-right:1px solid #edf1f5;text-align:center;color:#526071;font-size:13px}.vehicle-name{position:sticky;left:0;z-index:2;background:#fbfcfe;border-right:1px solid #e5eaf1;padding:12px;font-weight:800}.vehicle-name small{display:block;color:#667085;font-weight:400;margin-top:4px}.vehicle-row{position:relative;border-bottom:1px solid #edf1f5;min-height:86px}.slot{border-right:1px solid #edf1f5;min-height:86px}.eventbar{position:absolute;border:1px solid;border-radius:6px;padding:6px 8px;min-height:42px;overflow:hidden;font-size:12px;box-shadow:0 1px 2px rgba(16,24,40,.06);white-space:nowrap}.eventbar b{display:block;font-size:13px;margin-bottom:2px}.c-assigned{background:#eff6ff;border-color:#60a5fa;color:#1d4ed8}.c-completed{background:#ecfdf3;border-color:#34d399;color:#047857}.c-unsettled{background:#fff7ed;border-color:#fb923c;color:#c2410c}.c-settled{background:#f5f3ff;border-color:#a78bfa;color:#6d28d9}.tabs{display:flex;border:1px solid #d8e0ea;border-radius:7px;overflow:hidden}.tabs button{border:0;border-right:1px solid #d8e0ea;background:#fff;color:#344054;border-radius:0}.tabs button.active{background:#2563eb;color:#fff}.toast{position:fixed;right:24px;bottom:24px;background:#172433;color:#fff;border-radius:8px;padding:12px 14px;display:none}@media(max-width:1200px){.side{width:92px;padding:20px 10px}.brand{text-align:center;font-size:18px}.nav a{text-align:center;font-size:13px}.dispatch-grid{grid-template-columns:1fr}.dispatch-grid>.panel{height:auto;min-height:420px}main{padding:18px}}
  </style>
</head>
<body>
<div class="layout">
  <aside class="side"><div class="brand">调度<br>派单台</div><nav class="nav"><a class="active" href="#dispatch">派单</a><a href="#assigned">已分配</a><a href="#calendar">日历</a></nav></aside>
  <main>
    <section class="top"><div><h1>原地确认 + 接龙派单</h1><div class="sub">待派订单只保留核心列，其他字段统一进备注；选中订单后，右侧选司机和车辆，一键按时间路线顺序派单。</div></div><div class="pill" id="status">加载中</div></section>
    <section class="panel">
      <h2>解析订单 <small id="parseSummary">默认收起，用到时展开批量粘贴</small></h2>
      <div class="toolbar"><button class="secondary" id="parseToggle" onclick="toggleDrafts()">展开解析栏</button><button class="secondary" onclick="loadAll()">刷新</button><span class="hint">解析后的订单直接进入下面的待确认订单表，可修改后勾选派单。</span></div>
      <div class="details" id="draftBox"><textarea id="batchText" placeholder="一行一单，例如：3/22 09:00 大阪->京都 4人 50000"></textarea><div class="toolbar"><button onclick="parseBatch()">批量解析订单</button><button class="secondary" onclick="toggleDrafts()">收起解析栏</button></div></div>
    </section>
    <section class="dispatch-grid" id="dispatch">
      <div class="panel"><h2>待确认订单 <small>表格内修改，勾选后接龙派单</small></h2><div class="toolbar"><button class="secondary" onclick="selectAllPending()">全选</button><button class="secondary" onclick="clearSelected()">清空选择</button><span class="hint" id="selectedHint">未选择订单</span></div><div class="table-wrap"><table><thead><tr><th>选择</th><th>顺序</th><th>编号</th><th>开始日期/时间</th><th>结束日期/时间</th><th>路线</th><th>类型</th><th>车型</th><th>价格</th><th>备注</th></tr></thead><tbody id="pendingRows"></tbody></table></div></div>
      <div class="panel"><h2>选择司机 <small>点中选择</small></h2><div class="selected-box" id="driverPicked">未选司机</div><div class="list" id="driverList"></div></div>
      <div class="panel"><h2>选择车辆 <small>点中选择</small></h2><div class="selected-box" id="vehiclePicked">未选车辆</div><div class="selected-box" id="assignPreview">请选择订单、司机、车辆</div><div class="list" id="vehicleList"></div><button class="assign big" onclick="assignSelected()">确认分配</button></div>
    </section>
    <section class="panel" id="assigned"><h2>已分配订单池 <small>上面 3 个选择区派完后合并到这里</small></h2><div class="table-wrap"><table><thead><tr><th>订单号</th><th>开始</th><th>结束</th><th>路线</th><th>类型</th><th>车型</th><th>价格</th><th>司机</th><th>车辆</th><th>状态</th></tr></thead><tbody id="assignedRows"></tbody></table></div></section>
    <section class="panel" id="calendar"><h2>车辆占用日历 <small>24h / 7d / 30d</small></h2><div class="toolbar"><div class="tabs"><button id="tab-day" onclick="setView('day')">24h</button><button id="tab-week" onclick="setView('week')">7d</button><button id="tab-month" onclick="setView('month')">30d</button></div><input type="date" id="baseDate" onchange="loadAll()" /><select id="vehicleFilter" onchange="loadAll()"><option value="">全部车辆</option></select></div><div class="calendar-shell"><div id="calendarGrid"></div></div></section>
  </main>
</div>
<div class="toast" id="toast"></div>
<script>
const $=id=>document.getElementById(id);let state={view:'day',selected:new Set(),expanded:new Set(),editing:null,driver:null,vehicle:null,drafts:[],orders:[],drivers:[],vehicles:[],assignments:[],calendar:[]};
function today(){return new Date().toISOString().slice(0,10)}function toast(msg){const el=$('toast');el.textContent=msg;el.style.display='block';setTimeout(()=>el.style.display='none',2600)}
async function api(path,opts={}){const res=await fetch(path,{headers:{'Content-Type':'application/json'},...opts});const body=await res.json();if(!res.ok)throw new Error(body.error||res.statusText);return body}
function esc(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}function dadd(d,n){const x=new Date(d+'T00:00:00');x.setDate(x.getDate()+n);return x.toISOString().slice(0,10)}function minutes(t){if(!t||!t.includes(':'))return null;const [h,m]=t.split(':').map(Number);return h*60+m}function route(x){return `${x.pickup_location||'-'} -> ${x.dropoff_location||'-'}`}function keyOf(x){return `${x.kind}:${x.id}`}
function toggleDrafts(){const el=$('draftBox');const open=el.style.display!=='block';el.style.display=open?'block':'none';$('parseToggle').textContent=open?'收起解析栏':'展开解析栏';$('parseSummary').textContent=open?'批量粘贴订单文本，解析后进入待确认订单表':'默认收起，用到时展开批量粘贴'}function clearSelected(){state.selected.clear();renderPending();renderPreview()}
function setView(v){state.view=v;['day','week','month'].forEach(x=>$('tab-'+x).classList.toggle('active',x===v));loadAll()}
async function loadAll(){if(!$('baseDate').value)$('baseDate').value=today();const date=$('baseDate').value,vehicle=$('vehicleFilter').value;const [drafts,orders,drivers,vehicles,assignments,cal]=await Promise.all([api('/api/parser/drafts'),api('/api/dispatch/unassigned-orders'),api('/api/dispatch/drivers'),api('/api/dispatch/vehicles'),api('/api/dispatch/assignments'),api('/api/calendar/dispatch?view='+state.view+'&date='+date+(vehicle?'&vehicle_id='+vehicle:''))]);state.drafts=(drafts.drafts||[]).filter(x=>x.parse_status!=='confirmed'&&x.parse_status!=='discarded').map(x=>({kind:'draft',...x}));state.orders=(orders.orders||[]).map(x=>({kind:'order',...x}));state.drivers=drivers.drivers||[];state.vehicles=vehicles.vehicles||[];state.assignments=assignments.assignments||[];state.calendar=cal.items||[];render()}
function render(){renderVehicleOptions();renderPending();renderDrivers();renderVehicles();renderAssigned();renderCalendar();renderPreview();$('status').textContent=`待确认 ${state.drafts.length+state.orders.length} · 已分配 ${state.assignments.length}`}
function renderVehicleOptions(){const cur=$('vehicleFilter').value;$('vehicleFilter').innerHTML='<option value="">全部车辆</option>'+state.vehicles.map(v=>`<option value="${v.id}">${esc(v.plate_number)}</option>`).join('');$('vehicleFilter').value=cur}
function remark(x){return [`原文:${x.raw_text||''}`,`客人:${x.guest_name||''}`,`电话:${x.guest_contact||''}`,`人数:${x.passenger_count??''}`,`行李:${x.luggage_count??''}`,`旅行社:${x.agency_name||''}`,x.remark||''].filter(Boolean).join(' / ')}
function pendingRows(){const sorter=(a,b)=>Number(a.sequence||999)-Number(b.sequence||999)||String(a.order_date+a.start_time).localeCompare(String(b.order_date+b.start_time));return [...state.drafts.sort(sorter),...state.orders.sort(sorter)]}
function cellInput(x,k,t='text',cls='cell-input'){return `<input class="${cls}" data-row="${keyOf(x)}" data-key="${k}" type="${t}" value="${esc(x[k]??'')}" onclick="event.stopPropagation()" onchange="editCell(this)">`}
function cellText(x,k,cls='remark-input'){return `<textarea class="${cls}" data-row="${keyOf(x)}" data-key="${k}" onclick="event.stopPropagation()" onchange="editCell(this)">${esc(x[k]??'')}</textarea>`}
function renderPending(){const rows=pendingRows();$('pendingRows').innerHTML=rows.map((x,i)=>`<tr class="row-select ${state.selected.has(keyOf(x))?'active':''}" onclick="toggleRow('${keyOf(x)}')"><td onclick="event.stopPropagation()"><input type="checkbox" ${state.selected.has(keyOf(x))?'checked':''} onchange="toggleRow('${keyOf(x)}')"></td><td onclick="event.stopPropagation()"><input class="seq-input" type="number" value="${i+1}" onchange="setSeq('${keyOf(x)}',this.value)"></td><td>${cellInput(x,'oid')}<br><span class="tag">${x.kind==='draft'?'草稿':'订单'}</span></td><td>${cellInput(x,'order_date','date')}<br>${cellInput(x,'start_time','time')}</td><td>${cellInput(x,'end_date','date')}<br>${cellInput(x,'end_time','time')}</td><td>${cellInput(x,'pickup_location','text','route-input')}${cellInput(x,'dropoff_location','text','route-input')}</td><td>${cellInput(x,'order_type')}</td><td>${cellInput(x,'vehicle_type')}</td><td>${cellInput(x,'price','number')}</td><td>${cellText(x,'remark')}</td></tr>`).join('')||'<tr><td colspan="10" class="empty">待确认订单已清空</td></tr>';const selected=rows.filter(x=>state.selected.has(keyOf(x)));$('selectedHint').textContent=`已选择 ${selected.length} 单，派单顺序按“顺序”列执行`;renderPreview()}
function toggleRow(k){state.selected.has(k)?state.selected.delete(k):state.selected.add(k);renderPending()}
function selectAllPending(){pendingRows().forEach(x=>state.selected.add(keyOf(x)));renderPending()}
function setSeq(k,value){const row=[...state.drafts,...state.orders].find(x=>keyOf(x)===k);if(row)row.sequence=Number(value)||999;renderPending()}
function editCell(input){const row=[...state.drafts,...state.orders].find(x=>keyOf(x)===input.dataset.row);if(row)row[input.dataset.key]=input.value}
function renderDrivers(){const picked=state.drivers.find(d=>d.id===state.driver);$('driverPicked').textContent=picked?`已选：${picked.name}`:'未选司机';$('driverList').innerHTML=state.drivers.map(d=>`<div class="pick-card ${state.driver===d.id?'active':''}" onclick="state.driver=${d.id};renderDrivers();renderPreview()"><b>${esc(d.name)}</b><small>${esc(d.phone||'')} · ${esc(d.status)}</small></div>`).join('')||'<div class="empty">无可用司机</div>'}
function renderVehicles(){const picked=state.vehicles.find(v=>v.id===state.vehicle);$('vehiclePicked').textContent=picked?`已选：${picked.plate_number}`:'未选车辆';$('vehicleList').innerHTML=state.vehicles.map(v=>`<div class="pick-card ${state.vehicle===v.id?'active':''}" onclick="state.vehicle=${v.id};renderVehicles();renderPreview()"><b>${esc(v.plate_number)}</b><small>${esc(v.vehicle_type||'')} · ${esc(v.seat_count||'')}座</small></div>`).join('')||'<div class="empty">无可用车辆</div>'}
function renderPreview(){const rows=pendingRows().filter(x=>state.selected.has(keyOf(x)));const driver=state.drivers.find(d=>d.id===state.driver);const vehicle=state.vehicles.find(v=>v.id===state.vehicle);const total=rows.reduce((sum,x)=>sum+(Number(x.price)||0),0);$('assignPreview').innerHTML=rows.length&&driver&&vehicle?`<b>分配预览</b><br>订单：${rows.map(x=>esc(x.oid||x.id)).join(', ')}<br>司机：${esc(driver.name)}<br>车辆：${esc(vehicle.plate_number)}<br>预计收入：¥${total}`:'请选择订单、司机、车辆'}
function orderPayload(x){return {oid:x.oid,order_date:x.order_date,end_date:x.end_date,start_time:x.start_time,end_time:x.end_time,pickup_location:x.pickup_location,dropoff_location:x.dropoff_location,order_type:x.order_type,vehicle_type:x.vehicle_type,price:x.price,remark:x.remark}}
async function assignSelected(){const rows=pendingRows().filter(x=>state.selected.has(keyOf(x)));if(!rows.length)return toast('请先选择订单');if(!state.driver||!state.vehicle)return toast('请先选择司机和车辆');try{const orderIds=[];for(const x of rows){if(x.kind==='draft'){await api(`/api/parser/drafts/${x.id}`,{method:'PUT',body:JSON.stringify(orderPayload(x))});const r=await api(`/api/parser/drafts/${x.id}/confirm`,{method:'POST'});orderIds.push(r.order_id)}else{await api(`/api/orders/${x.id}`,{method:'PUT',body:JSON.stringify(orderPayload(x))});orderIds.push(x.id)}}const assigned=await api('/api/dispatch/assign',{method:'POST',body:JSON.stringify({order_ids:orderIds,driver_id:state.driver,vehicle_id:state.vehicle})});if(assigned.success===false)throw new Error('时间冲突，未派单');toast('接龙派单成功，司机端已同步');state.selected.clear();await loadAll()}catch(e){toast(e.message)}}
function renderAssigned(){$('assignedRows').innerHTML=state.assignments.map(x=>`<tr><td><b>${esc(x.oid||'-')}</b></td><td>${esc(x.order_date||'-')}<br>${esc(x.start_time||'')}</td><td>${esc(x.end_date||x.order_date||'-')}<br>${esc(x.end_time||'')}</td><td>${esc(route(x))}</td><td>${esc(x.order_type||'-')}</td><td>${esc(x.order_vehicle_type||x.assigned_vehicle_type||'-')}</td><td>${esc(x.price??'-')}</td><td>${esc(x.driver_name||'-')}</td><td>${esc(x.plate_number||'-')}</td><td><span class="tag">${esc(x.execution_status||x.status||'-')}</span></td></tr>`).join('')||'<tr><td colspan="10" class="empty">暂无已分配订单</td></tr>'}
function colorClass(x){if(['completed','returned'].includes(x.execution_status))return 'c-completed';if(['settled','paid'].includes(x.settlement_status))return 'c-settled';if(!['settled','paid'].includes(x.settlement_status))return 'c-unsettled';return 'c-assigned'}
function renderCalendar(){const cols=state.view==='day'?24:(state.view==='week'?7:30),dates=[...Array(cols)].map((_,i)=>dadd($('baseDate').value,i)),gridCols=`180px repeat(${cols}, 1fr)`;let html=`<div class="time-head" style="grid-template-columns:${gridCols}"><div class="head-cell">车辆</div>`+dates.map((d,i)=>`<div class="head-cell">${state.view==='day'?String(i).padStart(2,'0')+':00':d.slice(5)}</div>`).join('')+'</div>';for(const v of state.vehicles){const items=state.calendar.filter(x=>x.vehicle_id===v.id);html+=`<div class="vehicle-row" style="grid-template-columns:${gridCols};min-height:${Math.max(86,items.length*48+28)}px"><div class="vehicle-name">${esc(v.plate_number)}<small>${esc(v.vehicle_type||'')}</small></div>`+dates.map(()=>'<div class="slot"></div>').join('');items.forEach((x,i)=>{let left=180,width=90,label='';if(state.view==='day'){const s=minutes(x.start_time)??0,e=minutes(x.end_time)??1440;left=180+s/1440*1060;width=Math.max(80,(Math.max(e,s+60)-s)/1440*1060);label=`${x.start_time||''}-${x.end_time||''}`}else{const si=Math.max(0,dates.indexOf(x.order_date)),ei=Math.max(si,dates.indexOf(x.end_date||x.order_date));left=180+si/cols*1060;width=Math.max(90,(ei-si+1)/cols*1060);label=x.order_date===(x.end_date||x.order_date)?x.order_date:`${x.order_date} -> ${x.end_date}`}html+=`<div class="eventbar ${colorClass(x)}" style="left:${left}px;width:${width}px;top:${12+i*48}px"><b>${esc(x.oid||'')} ${esc(label)}</b><small>${esc(route(x))} · ${esc(x.driver_name||'-')}</small></div>`});html+='</div>'}$('calendarGrid').innerHTML=html}
async function parseBatch(){const lines=$('batchText').value.split(/\\n+/).map(x=>x.trim()).filter(Boolean);if(!lines.length)return toast('先粘贴订单文本');for(const text of lines){await api('/api/parser/text',{method:'POST',body:JSON.stringify({text})})}$('batchText').value='';toast(`已解析 ${lines.length} 条`);await loadAll()}
$('baseDate').value=today();setView('day');
</script>
</body>
</html>"""
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_dashboard_page(self) -> None:
        html = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>调度派单工作台</title>
  <style>
    *{box-sizing:border-box}body{margin:0;font-family:Arial,'Microsoft YaHei',sans-serif;background:#f5f7fb;color:#13213c}.layout{display:flex;min-height:100vh}.side{width:92px;background:#122033;color:#fff;padding:24px 14px;position:sticky;top:0;height:100vh}.brand{font-size:20px;font-weight:800;line-height:1.35;text-align:center;margin-bottom:30px}.nav a{display:block;color:#d7e2f1;text-decoration:none;text-align:center;padding:12px 6px;border-radius:7px;margin:7px 0}.nav a.active{background:#263d5c;color:#fff}main{flex:1;padding:18px 20px 40px}.panel{background:#fff;border:1px solid #dfe6f0;border-radius:8px;margin-bottom:12px;box-shadow:0 1px 2px rgba(16,24,40,.04)}.panel-head{display:flex;align-items:center;justify-content:space-between;padding:13px 16px;border-bottom:1px solid #edf1f6;gap:14px}.panel h2{font-size:18px;margin:0;white-space:nowrap}.panel h2 span{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;background:#2f6fed;color:#fff;font-size:13px;margin-right:8px}.body{padding:12px 16px}.toolbar{display:flex;gap:9px;align-items:center;flex-wrap:wrap}.toolbar input,.toolbar select{height:36px;border:1px solid #d5deea;border-radius:6px;padding:0 10px;background:#fff;color:#26384f}button{height:36px;border:0;border-radius:6px;padding:0 14px;font-weight:700;cursor:pointer;background:#2f6fed;color:#fff}button.secondary{background:#f1f5fb;color:#26384f;border:1px solid #d5deea}button.warn{background:#f59e0b}button.success{background:#16a34a}textarea{width:100%;min-height:88px;border:1px solid #d5deea;border-radius:7px;padding:10px;font-size:14px;resize:vertical}.details{display:none;margin-top:10px}.hint{font-size:13px;color:#667085}.table-wrap{overflow:auto;border:1px solid #e3e9f2;border-radius:7px}.pending-wrap{max-height:244px}.assigned-wrap{max-height:260px}table{width:100%;border-collapse:separate;border-spacing:0;min-width:1040px}#pending table{table-layout:fixed;min-width:1040px}#pending th:nth-child(1){width:46px}#pending th:nth-child(2){width:126px}#pending th:nth-child(3){width:58px}#pending th:nth-child(4),#pending th:nth-child(5){width:150px}#pending th:nth-child(6){width:190px}#pending th:nth-child(7){width:96px}#pending th:nth-child(8){width:110px}#pending th:nth-child(9){width:96px}#pending th:nth-child(10){width:168px}th{position:sticky;top:0;z-index:2;text-align:left;background:#f8fafc;color:#667085;font-size:12px;border-bottom:1px solid #e3e9f2;padding:7px 8px}td{border-bottom:1px solid #edf1f6;padding:5px 8px;font-size:13px;vertical-align:middle}.row.active{background:#eef6ff}.tag{display:inline-block;border:1px solid #d5deea;background:#f1f5fb;border-radius:14px;padding:2px 7px;font-size:12px;color:#334155}.cell-input{width:100%;height:28px;border:1px solid #d5deea;border-radius:5px;padding:0 7px;background:#fbfdff}.seq-input{width:44px}.route-input{width:100%;height:27px;border:1px solid #d5deea;border-radius:5px;padding:0 7px;margin-bottom:3px;background:#fbfdff}.remark-input{width:100%;height:36px;min-height:36px;border:1px solid #d5deea;border-radius:5px;padding:5px 7px;resize:none;background:#fbfdff}.resource-grid{display:grid;grid-template-columns:1fr 1.15fr 52px 1.15fr .95fr;gap:14px;align-items:stretch}.box{border:1px solid #e3e9f2;border-radius:8px;background:#fbfcfe;padding:12px;min-height:220px}.box h3{font-size:15px;margin:0 0 10px}.chipbox{display:flex;flex-wrap:wrap;gap:8px}.chip{background:#eef6ff;border:1px solid #bcd5ff;color:#1d4ed8;border-radius:6px;padding:7px 9px}.list{display:grid;gap:8px;max-height:260px;overflow:auto}.pick-card{border:1px solid #dfe6f0;border-radius:7px;background:#fff;padding:9px 10px;cursor:pointer}.pick-card.active{border-color:#16a34a;background:#eefaf2;box-shadow:0 0 0 2px rgba(22,163,74,.12)}.pick-card b{display:block}.pick-card small{color:#667085}.arrow{display:flex;align-items:center;justify-content:center;color:#2f6fed;font-size:34px}.preview{background:linear-gradient(135deg,#f0fdf4,#f8fffb);border-color:#ccebd7}.preview p{margin:8px 0;color:#26384f}.calendar-tools{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.tabs{display:flex;border:1px solid #d5deea;border-radius:7px;overflow:hidden}.tabs button{background:#fff;color:#26384f;border-radius:0;border-right:1px solid #d5deea}.tabs button.active{background:#2f6fed;color:#fff}.status-chips{flex:1;display:flex;justify-content:center;gap:8px;flex-wrap:wrap}.status-chip{border:1px solid;border-radius:7px;padding:7px 13px;font-weight:700;font-size:14px;background:#fff}.status-chip b{margin-left:8px;border:1px solid currentColor;border-radius:15px;padding:1px 8px}.s-unassigned{color:#f59e0b;background:#fff8ed}.s-assigned{color:#2563eb;background:#eff6ff}.s-completed{color:#16a34a;background:#effdf5}.s-unsettled{color:#ef4444;background:#fff1f2}.s-settled{color:#8b5cf6;background:#f5f3ff}.s-all{color:#475569;background:#f8fafc}.calendar-shell{overflow:auto;border:1px solid #dfe6f0;border-radius:8px;background:#fff;margin-top:10px}.time-head,.vehicle-row{display:grid;min-width:1220px}.time-head{position:sticky;top:0;background:#fff;z-index:3;border-bottom:1px solid #e3e9f2}.head-cell{padding:10px 8px;text-align:center;border-right:1px solid #edf1f6;color:#526071}.vehicle-name{position:sticky;left:0;z-index:2;background:#fbfcfe;border-right:1px solid #e3e9f2;padding:12px;font-weight:800}.vehicle-name small{display:block;color:#667085;font-weight:400}.vehicle-row{position:relative;border-bottom:1px solid #edf1f6;min-height:78px}.slot{border-right:1px solid #edf1f6}.eventbar{position:absolute;border:1px solid;border-radius:6px;padding:6px 8px;min-height:38px;font-size:12px;overflow:hidden;white-space:nowrap}.eventbar b{display:block}.c-assigned{background:#eff6ff;border-color:#60a5fa;color:#1d4ed8}.c-completed{background:#ecfdf3;border-color:#34d399;color:#047857}.c-unsettled{background:#fff7ed;border-color:#fb923c;color:#c2410c}.c-settled{background:#f5f3ff;border-color:#a78bfa;color:#6d28d9}.toast{position:fixed;right:24px;bottom:24px;background:#122033;color:#fff;border-radius:8px;padding:12px 14px;display:none}@media(max-width:1200px){.resource-grid{grid-template-columns:1fr}.arrow{display:none}.side{width:76px}main{padding:14px}.pending-wrap{max-height:360px}.status-chips{justify-content:flex-start}}
  </style>
</head>
<body>
<div class="layout">
  <aside class="side"><div class="brand">调度<br>派单台</div><nav class="nav"><a class="active" href="#pending">派单</a><a href="#assigned">已分配</a><a href="#calendar">日历</a></nav></aside>
  <main>
    <section class="panel" id="parse">
      <div class="panel-head"><h2><span>1</span>解析订单</h2><div class="toolbar"><button class="secondary" id="parseToggle" onclick="toggleParse()">展开解析栏</button><button class="secondary" onclick="loadAll()">刷新</button><span class="hint" id="parseSummary">默认收起，使用时展开批量粘贴</span></div></div>
      <div class="body details" id="parseBox"><textarea id="batchText" placeholder="一行一单，例如：3/22 09:00 大阪->京都 4人 50000"></textarea><div class="toolbar" style="margin-top:10px"><button onclick="parseBatch()">批量解析订单</button><button class="secondary" onclick="toggleParse()">收起</button></div></div>
    </section>
    <section class="panel" id="pending">
      <div class="panel-head"><h2><span>2</span>待确认订单（草稿解析）</h2><div class="toolbar"><input type="date" id="filterStart"><input type="date" id="filterEnd"><input id="keyword" placeholder="订单号/客户/手机号"><select id="statusFilter"><option>全部状态</option><option>未派车</option><option>已派车</option></select><button class="success" onclick="assignSelected()">一键排单</button><button class="warn" onclick="confirmSelected()">原地确认</button></div></div>
      <div class="body"><div class="toolbar" style="margin-bottom:10px"><button class="secondary" onclick="selectAllPending()">全选</button><button class="secondary" onclick="clearSelected()">清空选择</button><span class="hint" id="selectedHint">未选择订单</span></div><div class="table-wrap pending-wrap"><table><thead><tr><th>选择</th><th>编号</th><th>开始日期/时间</th><th>结束日期/时间</th><th>路线</th><th>类型</th><th>车型</th><th>价格(¥)</th><th>备注</th><th>操作</th></tr></thead><tbody id="pendingRows"></tbody></table></div></div>
    </section>
    <section class="panel">
      <div class="panel-head"><h2><span>3</span>分配资源（选择司机 + 车辆）</h2><span class="hint">选中订单后点司机和车辆，右侧确认分配</span></div>
      <div class="body resource-grid"><div class="box"><h3>订单选择</h3><div class="chipbox" id="orderChips"></div></div><div class="box"><h3>选择司机</h3><div class="list" id="driverList"></div></div><div class="arrow">→</div><div class="box"><h3>选择车辆</h3><div class="list" id="vehicleList"></div></div><div class="box preview"><h3>分配预览</h3><div id="assignPreview">请选择订单、司机、车辆</div><button class="success" style="width:100%;margin-top:12px" onclick="assignSelected()">确认分配</button></div></div>
    </section>
    <section class="panel" id="assigned">
      <div class="panel-head"><h2><span>4</span>已分配订单池</h2><div class="toolbar"><select><option>全部司机</option></select><select><option>全部车辆</option></select><input type="date"><input placeholder="搜索订单号/客户"><button class="secondary">导出</button></div></div>
      <div class="body"><div class="table-wrap assigned-wrap"><table><thead><tr><th>编号</th><th>开始日期/时间</th><th>结束日期/时间</th><th>路线</th><th>类型</th><th>车型</th><th>司机</th><th>车辆</th><th>价格(¥)</th><th>状态</th><th>备注</th></tr></thead><tbody id="assignedRows"></tbody></table></div></div>
    </section>
    <section class="panel" id="calendar">
      <div class="panel-head"><h2><span>5</span>日历排程（按车辆视图）</h2><div class="status-chips" id="calendarStatus"></div><div class="calendar-tools"><div class="tabs"><button id="tab-day" onclick="setView('day')">24h</button><button id="tab-week" onclick="setView('week')">7d</button><button id="tab-month" onclick="setView('month')">30d</button></div><input type="date" id="baseDate" onchange="loadAll()"><select id="vehicleFilter" onchange="loadAll()"><option value="">全部车辆</option></select></div></div>
      <div class="body"><div class="calendar-shell"><div id="calendarGrid"></div></div></div>
    </section>
  </main>
</div>
<div class="toast" id="toast"></div>
<script>
const $=id=>document.getElementById(id);let state={view:'day',selected:new Set(),driver:null,vehicle:null,drafts:[],orders:[],drivers:[],vehicles:[],assignments:[],calendar:[]};
function today(){return new Date().toISOString().slice(0,10)}function toast(msg){const el=$('toast');el.textContent=msg;el.style.display='block';setTimeout(()=>el.style.display='none',2600)}
async function api(path,opts={}){const res=await fetch(path,{headers:{'Content-Type':'application/json'},...opts});const body=await res.json();if(!res.ok)throw new Error(body.error||res.statusText);return body}
function esc(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}function dadd(d,n){const x=new Date(d+'T00:00:00');x.setDate(x.getDate()+n);return x.toISOString().slice(0,10)}function minutes(t){if(!t||!t.includes(':'))return null;const [h,m]=t.split(':').map(Number);return h*60+m}function route(x){return `${x.pickup_location||'-'} -> ${x.dropoff_location||'-'}`}function keyOf(x){return `${x.kind}:${x.id}`}
function toggleParse(){const el=$('parseBox');const open=el.style.display!=='block';el.style.display=open?'block':'none';$('parseToggle').textContent=open?'收起解析栏':'展开解析栏';$('parseSummary').textContent=open?'批量粘贴订单文本，解析后进入待确认订单表':'默认收起，使用时展开批量粘贴'}
function setView(v){state.view=v;['day','week','month'].forEach(x=>$('tab-'+x).classList.toggle('active',x===v));loadAll()}
async function loadAll(){if(!$('baseDate').value)$('baseDate').value=today();const date=$('baseDate').value,vehicle=$('vehicleFilter').value;const [drafts,orders,drivers,vehicles,assignments,cal]=await Promise.all([api('/api/parser/drafts'),api('/api/dispatch/unassigned-orders'),api('/api/dispatch/drivers'),api('/api/dispatch/vehicles'),api('/api/dispatch/assignments'),api('/api/calendar/dispatch?view='+state.view+'&date='+date+(vehicle?'&vehicle_id='+vehicle:''))]);state.drafts=(drafts.drafts||[]).filter(x=>x.parse_status!=='confirmed'&&x.parse_status!=='discarded').map(x=>({kind:'draft',...x}));state.orders=(orders.orders||[]).map(x=>({kind:'order',...x}));state.drivers=drivers.drivers||[];state.vehicles=vehicles.vehicles||[];state.assignments=assignments.assignments||[];state.calendar=cal.items||[];render()}
function render(){renderVehicleOptions();renderPending();renderDrivers();renderVehicles();renderPreview();renderAssigned();renderCalendarStatus();renderCalendar()}
function renderVehicleOptions(){const cur=$('vehicleFilter').value;$('vehicleFilter').innerHTML='<option value="">全部车辆</option>'+state.vehicles.map(v=>`<option value="${v.id}">${esc(v.plate_number)}</option>`).join('');$('vehicleFilter').value=cur}
function pendingRows(){const sorter=(a,b)=>String(a.order_date+a.start_time).localeCompare(String(b.order_date+b.start_time));return [...state.drafts.sort(sorter),...state.orders.sort(sorter)]}
function fmtOid(x){const raw=String(x.oid||x.id||'');return raw.replace(/^20(\\d{6})/,'$1')}
function briefRemark(x){return String(x.remark||x.raw_text||'').replace(/\\s+/g,' ').slice(0,80)}
function editInput(x,k,t='text'){return `<input class="cell-input" data-row="${keyOf(x)}" data-key="${k}" type="${t}" value="${esc(x[k]??'')}" onclick="event.stopPropagation()" onchange="editCell(this)">`}
function editRoute(x){return `${editInput(x,'pickup_location')}<br>${editInput(x,'dropoff_location')}`}
function detailRow(x){return `<tr class="detail-row"><td colspan="10"><div class="detail-box"><b>完整解析内容</b><span>客人：${esc(x.guest_name||'-')}</span><span>导游/联系人：${esc(x.guide_name||x.contact_name||'-')}</span><span>联系方式：${esc(x.guest_contact||x.contact_phone||'-')}</span><span>人数：${esc(x.passenger_count??'-')}</span><span>行李：${esc(x.luggage_count??'-')}</span><span>旅行社：${esc(x.agency_name||'-')}</span><span>原文：${esc(x.raw_text||'-')}</span><p>${esc(x.remark||'')}</p></div></td></tr>`}
function renderPending(){const rows=pendingRows();let html='';for(const x of rows){const k=keyOf(x),isEdit=state.editing===k;html+=`<tr class="row ${state.selected.has(k)?'active':''}" onclick="toggleRow('${k}')"><td onclick="event.stopPropagation()"><input type="checkbox" ${state.selected.has(k)?'checked':''} onchange="toggleRow('${k}')"></td><td><b>${esc(fmtOid(x))}</b></td><td>${isEdit?editInput(x,'order_date','date')+'<br>'+editInput(x,'start_time','time'):`${esc(x.order_date||'-')}<br><span class="muted">${esc(x.start_time||'-')}</span>`}</td><td>${isEdit?editInput(x,'end_date','date')+'<br>'+editInput(x,'end_time','time'):`${esc(x.end_date||x.order_date||'-')}<br><span class="muted">${esc(x.end_time||'-')}</span>`}</td><td>${isEdit?editRoute(x):`<span class="text-cell">${esc(route(x))}</span>`}</td><td>${isEdit?editInput(x,'order_type'):`${esc(x.order_type||'-')}`}</td><td>${isEdit?editInput(x,'vehicle_type'):`${esc(x.vehicle_type||'-')}`}</td><td>${isEdit?editInput(x,'price','number'):`${esc(x.price??'-')}`}</td><td>${isEdit?`<textarea class="remark-input" data-row="${k}" data-key="remark" onclick="event.stopPropagation()" onchange="editCell(this)">${esc(x.remark??'')}</textarea>`:`<span class="ellipsis">${esc(briefRemark(x))}</span>`}</td><td onclick="event.stopPropagation()" class="op-cell">${isEdit?`<button class="link-btn" onclick="saveEdit('${k}')">保存</button><button class="link-btn" onclick="cancelEdit()">取消</button>`:`<button class="link-btn" onclick="toggleExpand('${k}')">${state.expanded.has(k)?'收起':'展开'}</button><button class="link-btn" onclick="confirmOne('${k}')">确认</button><button class="link-btn" onclick="startEdit('${k}')">编辑</button>`}</td></tr>`;if(state.expanded.has(k))html+=detailRow(x)}$('pendingRows').innerHTML=html||'<tr><td colspan="10" style="text-align:center;color:#98a2b3;padding:24px">暂无待确认订单</td></tr>';const selected=rows.filter(x=>state.selected.has(keyOf(x)));$('selectedHint').textContent=`已选择 ${selected.length} 单`;renderPreview()}
function findPending(k){return [...state.drafts,...state.orders].find(x=>keyOf(x)===k)}
function toggleRow(k){state.selected.has(k)?state.selected.delete(k):state.selected.add(k);renderPending()}function selectAllPending(){pendingRows().forEach(x=>state.selected.add(keyOf(x)));renderPending()}function clearSelected(){state.selected.clear();renderPending()}
function toggleExpand(k){state.expanded.has(k)?state.expanded.delete(k):state.expanded.add(k);renderPending()}function startEdit(k){state.editing=k;renderPending()}function cancelEdit(){state.editing=null;loadAll()}
function editCell(input){const row=findPending(input.dataset.row);if(row)row[input.dataset.key]=input.value}
function renderDrivers(){const picked=state.drivers.find(d=>d.id===state.driver);$('driverList').innerHTML=state.drivers.map(d=>`<div class="pick-card ${state.driver===d.id?'active':''}" onclick="state.driver=${d.id};renderDrivers();renderPreview()"><b>${esc(d.name)}</b><small>${esc(d.phone||'')} · ${esc(d.status)}</small></div>`).join('')||'<div style="color:#98a2b3">无可用司机</div>'}
function renderVehicles(){$('vehicleList').innerHTML=state.vehicles.map(v=>`<div class="pick-card ${state.vehicle===v.id?'active':''}" onclick="state.vehicle=${v.id};renderVehicles();renderPreview()"><b>${esc(v.plate_number)}</b><small>${esc(v.vehicle_type||'')} · ${esc(v.seat_count||'')}座</small></div>`).join('')||'<div style="color:#98a2b3">无可用车辆</div>'}
function selectedRows(){return pendingRows().filter(x=>state.selected.has(keyOf(x)))}function renderPreview(){const rows=selectedRows(),driver=state.drivers.find(d=>d.id===state.driver),vehicle=state.vehicles.find(v=>v.id===state.vehicle),total=rows.reduce((s,x)=>s+(Number(x.price)||0),0);$('orderChips').innerHTML=rows.map(x=>`<span class="chip">${esc(x.oid||x.id)}</span>`).join('')||'<span class="hint">点击待确认订单勾选</span>';$('assignPreview').innerHTML=rows.length&&driver&&vehicle?`<p>订单：${rows.map(x=>esc(x.oid||x.id)).join(', ')}</p><p>司机：${esc(driver.name)}</p><p>车辆：${esc(vehicle.plate_number)}</p><p>预计收入：¥${total}</p>`:'请选择订单、司机、车辆'}
function orderPayload(x){return {oid:x.oid,order_date:x.order_date,end_date:x.end_date,start_time:x.start_time,end_time:x.end_time,pickup_location:x.pickup_location,dropoff_location:x.dropoff_location,order_type:x.order_type,vehicle_type:x.vehicle_type,price:x.price,remark:x.remark}}
async function assignSelected(){const rows=selectedRows();if(!rows.length)return toast('请先选择订单');if(!state.driver||!state.vehicle)return toast('请先选择司机和车辆');try{const orderIds=[];for(const x of rows){if(x.kind==='draft'){await api(`/api/parser/drafts/${x.id}`,{method:'PUT',body:JSON.stringify(orderPayload(x))});const r=await api(`/api/parser/drafts/${x.id}/confirm`,{method:'POST'});orderIds.push(r.order_id)}else{await api(`/api/orders/${x.id}`,{method:'PUT',body:JSON.stringify(orderPayload(x))});orderIds.push(x.id)}}const assigned=await api('/api/dispatch/assign',{method:'POST',body:JSON.stringify({order_ids:orderIds,driver_id:state.driver,vehicle_id:state.vehicle})});if(assigned.success===false)throw new Error('时间冲突，未派单');toast('分配成功，司机端已同步');state.selected.clear();await loadAll()}catch(e){toast(e.message)}}
function renderAssigned(){$('assignedRows').innerHTML=state.assignments.map(x=>`<tr><td><b>${esc(x.oid||'-')}</b></td><td>${esc(x.order_date||'-')} ${esc(x.start_time||'')}</td><td>${esc(x.end_date||x.order_date||'-')} ${esc(x.end_time||'')}</td><td>${esc(route(x))}</td><td>${esc(x.order_type||'-')}</td><td>${esc(x.order_vehicle_type||x.assigned_vehicle_type||'-')}</td><td>${esc(x.driver_name||'-')}</td><td>${esc(x.plate_number||'-')}</td><td>${esc(x.price??'-')}</td><td><span class="tag">${esc(x.execution_status||x.status||'-')}</span></td><td>${esc(x.remark||'')}</td></tr>`).join('')||'<tr><td colspan="11" style="text-align:center;color:#98a2b3;padding:24px">暂无已分配订单</td></tr>'}
function renderCalendarStatus(){const assigned=state.assignments.length,unassigned=state.orders.length,completed=state.assignments.filter(x=>['completed','returned'].includes(x.execution_status)).length,settled=state.assignments.filter(x=>['settled','paid'].includes(x.settlement_status)).length,unsettled=state.assignments.filter(x=>!['settled','paid'].includes(x.settlement_status)).length,total=assigned+unassigned;const chips=[['s-unassigned','未派车',unassigned],['s-assigned','已派车',assigned],['s-completed','已完成',completed],['s-unsettled','未结账',unsettled],['s-settled','已结账',settled],['s-all','全部',total]];$('calendarStatus').innerHTML=chips.map(x=>`<div class="status-chip ${x[0]}">${x[1]}<b>${x[2]}</b></div>`).join('')}
function colorClass(x){if(['completed','returned'].includes(x.execution_status))return 'c-completed';if(['settled','paid'].includes(x.settlement_status))return 'c-settled';if(!['settled','paid'].includes(x.settlement_status))return 'c-unsettled';return 'c-assigned'}
function renderCalendar(){const cols=state.view==='day'?24:(state.view==='week'?7:30),dates=[...Array(cols)].map((_,i)=>dadd($('baseDate').value,i)),gridCols=`180px repeat(${cols}, 1fr)`;let html=`<div class="time-head" style="grid-template-columns:${gridCols}"><div class="head-cell">车辆</div>`+dates.map((d,i)=>`<div class="head-cell">${state.view==='day'?String(i).padStart(2,'0')+':00':d.slice(5)}</div>`).join('')+'</div>';for(const v of state.vehicles){const items=state.calendar.filter(x=>x.vehicle_id===v.id);html+=`<div class="vehicle-row" style="grid-template-columns:${gridCols};min-height:${Math.max(78,items.length*44+22)}px"><div class="vehicle-name">${esc(v.plate_number)}<small>${esc(v.vehicle_type||'')}</small></div>`+dates.map(()=>'<div class="slot"></div>').join('');items.forEach((x,i)=>{let left=180,width=90,label='';if(state.view==='day'){const s=minutes(x.start_time)??0,e=minutes(x.end_time)??1440;left=180+s/1440*1040;width=Math.max(80,(Math.max(e,s+60)-s)/1440*1040);label=`${x.start_time||''}-${x.end_time||''}`}else{const si=Math.max(0,dates.indexOf(x.order_date)),ei=Math.max(si,dates.indexOf(x.end_date||x.order_date));left=180+si/cols*1040;width=Math.max(90,(ei-si+1)/cols*1040);label=x.order_date===(x.end_date||x.order_date)?x.order_date:`${x.order_date} -> ${x.end_date}`}html+=`<div class="eventbar ${colorClass(x)}" style="left:${left}px;width:${width}px;top:${10+i*44}px"><b>${esc(x.oid||'')} ${esc(label)}</b><small>${esc(route(x))}</small></div>`});html+='</div>'}$('calendarGrid').innerHTML=html}
async function parseBatch(){const lines=$('batchText').value.split(/\\n+/).map(x=>x.trim()).filter(Boolean);if(!lines.length)return toast('先粘贴订单文本');for(const text of lines){await api('/api/parser/text',{method:'POST',body:JSON.stringify({text})})}$('batchText').value='';toast(`已解析 ${lines.length} 条`);await loadAll()}
$('baseDate').value=today();setView('day');
</script>
</body>
</html>"""
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_dashboard_page(self) -> None:
        html = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>调度派单工作台</title>
  <style>
    *{box-sizing:border-box}body{margin:0;font-family:Arial,'Microsoft YaHei',sans-serif;background:#f5f7fb;color:#14213d}.layout{display:flex;min-height:100vh}.side{width:92px;background:#122033;color:white;padding:24px 14px;position:sticky;top:0;height:100vh}.brand{font-size:20px;font-weight:800;line-height:1.35;text-align:center;margin-bottom:30px}.nav a{display:block;color:#d7e2f1;text-decoration:none;text-align:center;padding:12px 6px;border-radius:7px;margin:7px 0}.nav a.active{background:#263d5c}.main{flex:1;padding:18px 20px 40px}.panel{background:white;border:1px solid #dfe6f0;border-radius:8px;margin-bottom:12px;box-shadow:0 1px 2px rgba(16,24,40,.04)}.head{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:13px 16px;border-bottom:1px solid #edf1f6}.head h2{margin:0;font-size:18px;white-space:nowrap}.num{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;background:#2f6fed;color:white;font-size:13px;margin-right:8px}.body{padding:12px 16px}.toolbar{display:flex;gap:9px;align-items:center;flex-wrap:wrap}.toolbar input,.toolbar select{height:36px;border:1px solid #d5deea;border-radius:6px;padding:0 10px;background:white;color:#26384f}button{height:36px;border:0;border-radius:6px;padding:0 14px;font-weight:700;cursor:pointer;background:#2f6fed;color:white}button.secondary{background:#f1f5fb;color:#26384f;border:1px solid #d5deea}button.warn{background:#f59e0b}button.success{background:#16a34a}.hint{font-size:13px;color:#667085}textarea{width:100%;min-height:88px;border:1px solid #d5deea;border-radius:7px;padding:10px;font-size:14px;resize:vertical}.hidden{display:none}.table-wrap{overflow:auto;border:1px solid #e3e9f2;border-radius:7px}.pending-wrap{max-height:300px}.assigned-wrap{max-height:260px}table{width:100%;border-collapse:separate;border-spacing:0;min-width:1120px}th{position:sticky;top:0;z-index:2;text-align:left;background:#f8fafc;color:#667085;font-size:12px;border-bottom:1px solid #e3e9f2;padding:8px}td{border-bottom:1px solid #edf1f6;padding:8px;font-size:13px;vertical-align:middle;height:48px}.row.active{background:#eef6ff}.muted{color:#667085}.ellipsis{display:block;max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.op{white-space:nowrap}.link-btn{height:auto;background:transparent;color:#2563eb;padding:0 5px;border:0}.cell-input{width:100%;height:30px;border:1px solid #d5deea;border-radius:5px;padding:0 7px}.route-input{width:100%;height:30px;border:1px solid #d5deea;border-radius:5px;padding:0 7px;margin-bottom:4px}.remark-input{width:100%;height:44px;border:1px solid #d5deea;border-radius:5px;padding:6px;resize:vertical}.detail-row td{height:auto;background:#fbfdff}.detail-box{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:8px;line-height:1.5}.detail-box b,.detail-box p{grid-column:1/-1;margin:0}.resource-grid{display:grid;grid-template-columns:1fr 1.1fr 42px 1.1fr .95fr;gap:14px}.box{border:1px solid #e3e9f2;border-radius:8px;background:#fbfcfe;padding:12px;min-height:220px}.box h3{font-size:15px;margin:0 0 10px}.chipbox{display:flex;flex-wrap:wrap;gap:8px}.chip{background:#eef6ff;border:1px solid #bcd5ff;color:#1d4ed8;border-radius:6px;padding:7px 9px}.list{display:grid;gap:8px;max-height:260px;overflow:auto}.pick-card{border:1px solid #dfe6f0;border-radius:7px;background:white;padding:9px 10px;cursor:pointer}.pick-card.active{border-color:#16a34a;background:#eefaf2;box-shadow:0 0 0 2px rgba(22,163,74,.12)}.pick-card b{display:block}.pick-card small{color:#667085}.arrow{display:flex;align-items:center;justify-content:center;color:#2f6fed;font-size:30px}.preview{background:linear-gradient(135deg,#f0fdf4,#f8fffb);border-color:#ccebd7}.status-chips{flex:1;display:flex;justify-content:center;gap:8px;flex-wrap:wrap}.status-chip{border:1px solid;border-radius:7px;padding:7px 13px;font-weight:700;font-size:14px}.status-chip b{margin-left:8px;border:1px solid currentColor;border-radius:15px;padding:1px 8px}.s-unassigned{color:#f59e0b;background:#fff8ed}.s-assigned{color:#2563eb;background:#eff6ff}.s-completed{color:#16a34a;background:#effdf5}.s-unsettled{color:#ef4444;background:#fff1f2}.s-settled{color:#8b5cf6;background:#f5f3ff}.s-all{color:#475569;background:#f8fafc}.tabs{display:flex;border:1px solid #d5deea;border-radius:7px;overflow:hidden}.tabs button{background:white;color:#26384f;border-radius:0;border-right:1px solid #d5deea}.tabs button.active{background:#2f6fed;color:white}.calendar-shell{overflow:auto;border:1px solid #dfe6f0;border-radius:8px;background:white;margin-top:10px}.time-head,.vehicle-row{display:grid;min-width:1220px}.time-head{position:sticky;top:0;background:white;z-index:3;border-bottom:1px solid #e3e9f2}.head-cell{padding:10px 8px;text-align:center;border-right:1px solid #edf1f6;color:#526071}.vehicle-name{position:sticky;left:0;z-index:2;background:#fbfcfe;border-right:1px solid #e3e9f2;padding:12px;font-weight:800}.vehicle-name small{display:block;color:#667085;font-weight:400}.vehicle-row{position:relative;border-bottom:1px solid #edf1f6;min-height:78px}.slot{border-right:1px solid #edf1f6}.eventbar{position:absolute;border:1px solid;border-radius:6px;padding:6px 8px;min-height:38px;font-size:12px;overflow:hidden;white-space:nowrap}.c-assigned{background:#eff6ff;border-color:#60a5fa;color:#1d4ed8}.c-completed{background:#ecfdf3;border-color:#34d399;color:#047857}.c-unsettled{background:#fff7ed;border-color:#fb923c;color:#c2410c}.c-settled{background:#f5f3ff;border-color:#a78bfa;color:#6d28d9}.toast{position:fixed;right:24px;bottom:24px;background:#122033;color:white;border-radius:8px;padding:12px 14px;display:none}@media(max-width:1200px){.resource-grid{grid-template-columns:1fr}.arrow{display:none}.side{width:76px}.main{padding:14px}.status-chips{justify-content:flex-start}}
  </style>
</head>
<body>
<div class="layout">
  <aside class="side"><div class="brand">调度<br>派单台</div><nav class="nav"><a class="active" href="#pending">派单</a><a href="#assigned">已分配</a><a href="#calendar">日历</a></nav></aside>
  <main class="main">
    <section class="panel"><div class="head"><h2><span class="num">1</span>解析订单</h2><div class="toolbar"><button class="secondary" id="parseToggle" onclick="toggleParse()">展开解析栏</button><button class="secondary" onclick="loadAll()">刷新</button><span class="hint" id="parseSummary">默认收起，使用时展开批量粘贴</span></div></div><div class="body hidden" id="parseBox"><textarea id="batchText" placeholder="一行一单，例如：3/22 09:00 大阪->京都 4人 50000"></textarea><div class="toolbar" style="margin-top:10px"><button onclick="parseBatch()">批量解析订单</button><button class="secondary" onclick="toggleParse()">收起</button></div></div></section>
    <section class="panel" id="pending"><div class="head"><h2><span class="num">2</span>待确认订单（草稿解析）</h2><div class="toolbar"><input type="date"><input type="date"><input placeholder="订单号/客户/手机号"><select><option>全部状态</option><option>未派车</option><option>已派车</option></select><button class="success" onclick="assignSelected()">一键排单</button><button class="warn" onclick="confirmSelected()">原地确认</button></div></div><div class="body"><div class="toolbar" style="margin-bottom:10px"><button class="secondary" onclick="selectAllPending()">全选</button><button class="secondary" onclick="clearSelected()">清空选择</button><span class="hint" id="selectedHint">未选择订单</span></div><div class="table-wrap pending-wrap"><table><thead><tr><th>选择</th><th>编号</th><th>开始日期/时间</th><th>结束日期/时间</th><th>路线</th><th>类型</th><th>车型</th><th>价格</th><th>备注</th><th>操作</th></tr></thead><tbody id="pendingRows"></tbody></table></div></div></section>
    <section class="panel"><div class="head"><h2><span class="num">3</span>分配资源（选择司机 + 车辆）</h2><span class="hint">选中订单后点司机和车辆，右侧确认分配</span></div><div class="body resource-grid"><div class="box"><h3>订单选择</h3><div class="chipbox" id="orderChips"></div></div><div class="box"><h3>选择司机</h3><div class="list" id="driverList"></div></div><div class="arrow">→</div><div class="box"><h3>选择车辆</h3><div class="list" id="vehicleList"></div></div><div class="box preview"><h3>分配预览</h3><div id="assignPreview">请选择订单、司机、车辆</div><button class="success" style="width:100%;margin-top:12px" onclick="assignSelected()">确认分配</button></div></div></section>
    <section class="panel" id="assigned"><div class="head"><h2><span class="num">4</span>已分配订单池</h2><div class="toolbar"><select><option>全部司机</option></select><select><option>全部车辆</option></select><input type="date"><input placeholder="搜索订单号/客户"><button class="secondary">导出</button></div></div><div class="body"><div class="table-wrap assigned-wrap"><table><thead><tr><th>编号</th><th>开始日期/时间</th><th>结束日期/时间</th><th>路线</th><th>类型</th><th>车型</th><th>司机</th><th>车辆</th><th>价格</th><th>状态</th><th>备注</th></tr></thead><tbody id="assignedRows"></tbody></table></div></div></section>
    <section class="panel" id="calendar"><div class="head"><h2><span class="num">5</span>日历排程（按车辆视图）</h2><div class="status-chips" id="calendarStatus"></div><div class="toolbar"><div class="tabs"><button id="tab-day" onclick="setView('day')">24h</button><button id="tab-week" onclick="setView('week')">7d</button><button id="tab-month" onclick="setView('month')">30d</button></div><input type="date" id="baseDate" onchange="loadAll()"><select id="vehicleFilter" onchange="loadAll()"><option value="">全部车辆</option></select></div></div><div class="body"><div class="calendar-shell"><div id="calendarGrid"></div></div></div></section>
  </main>
</div>
<div class="toast" id="toast"></div>
<script>
const $=id=>document.getElementById(id);let state={view:'day',selected:new Set(),expanded:new Set(),editing:null,driver:null,vehicle:null,drafts:[],orders:[],drivers:[],vehicles:[],assignments:[],calendar:[]};
function today(){return new Date().toISOString().slice(0,10)}function toast(m){const e=$('toast');e.textContent=m;e.style.display='block';setTimeout(()=>e.style.display='none',2400)}
async function api(path,opts={}){const r=await fetch(path,{headers:{'Content-Type':'application/json'},...opts});const b=await r.json();if(!r.ok)throw new Error(b.error||r.statusText);return b}
function esc(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
function keyOf(x){return `${x.kind}:${x.id}`}function route(x){return `${x.pickup_location||'-'} -> ${x.dropoff_location||'-'}`}function dadd(d,n){const x=new Date(d+'T00:00:00');x.setDate(x.getDate()+n);return x.toISOString().slice(0,10)}function minutes(t){if(!t||!t.includes(':'))return null;const [h,m]=t.split(':').map(Number);return h*60+m}
function toggleParse(){const e=$('parseBox'),open=e.classList.contains('hidden');e.classList.toggle('hidden',!open);$('parseToggle').textContent=open?'收起解析栏':'展开解析栏';$('parseSummary').textContent=open?'批量粘贴订单文本，解析后进入待确认订单表':'默认收起，使用时展开批量粘贴'}
function setView(v){state.view=v;['day','week','month'].forEach(x=>$('tab-'+x).classList.toggle('active',x===v));loadAll()}
async function loadAll(){if(!$('baseDate').value)$('baseDate').value=today();const date=$('baseDate').value,vehicle=$('vehicleFilter').value;const [drafts,orders,drivers,vehicles,assignments,cal]=await Promise.all([api('/api/parser/drafts'),api('/api/dispatch/unassigned-orders'),api('/api/dispatch/drivers'),api('/api/dispatch/vehicles'),api('/api/dispatch/assignments'),api('/api/calendar/dispatch?view='+state.view+'&date='+date+(vehicle?'&vehicle_id='+vehicle:''))]);state.drafts=(drafts.drafts||[]).filter(x=>x.parse_status!=='confirmed'&&x.parse_status!=='discarded').map(x=>({kind:'draft',...x}));state.orders=(orders.orders||[]).map(x=>({kind:'order',...x}));state.drivers=drivers.drivers||[];state.vehicles=vehicles.vehicles||[];state.assignments=assignments.assignments||[];state.calendar=cal.items||[];render()}
function render(){renderVehicleOptions();renderPending();renderDrivers();renderVehicles();renderPreview();renderAssigned();renderCalendarStatus();renderCalendar()}
function renderVehicleOptions(){const cur=$('vehicleFilter').value;$('vehicleFilter').innerHTML='<option value="">全部车辆</option>'+state.vehicles.map(v=>`<option value="${v.id}">${esc(v.plate_number)}</option>`).join('');$('vehicleFilter').value=cur}
function pendingRows(){return [...state.drafts,...state.orders].sort((a,b)=>String(a.order_date+a.start_time).localeCompare(String(b.order_date+b.start_time)))}
function fmtOid(x){return String(x.oid||x.id||'').replace(/^20(\\d{6})/,'$1')}function brief(x){return String(x.remark||x.raw_text||'').replace(/\\s+/g,' ').slice(0,90)}
function findPending(k){return [...state.drafts,...state.orders].find(x=>keyOf(x)===k)}function payload(x){return {oid:x.oid,order_date:x.order_date,end_date:x.end_date,start_time:x.start_time,end_time:x.end_time,pickup_location:x.pickup_location,dropoff_location:x.dropoff_location,order_type:x.order_type,vehicle_type:x.vehicle_type,price:x.price,remark:x.remark}}
function editInput(x,k,t='text'){return `<input class="cell-input" data-row="${keyOf(x)}" data-key="${k}" type="${t}" value="${esc(x[k]??'')}" onclick="event.stopPropagation()" onchange="editCell(this)">`}
function detailRow(x){return `<tr class="detail-row"><td colspan="10"><div class="detail-box"><b>完整解析内容</b><span>客人：${esc(x.guest_name||'-')}</span><span>导游/联系人：${esc(x.guide_name||x.contact_name||'-')}</span><span>联系方式：${esc(x.guest_contact||x.contact_phone||'-')}</span><span>人数：${esc(x.passenger_count??'-')}</span><span>行李：${esc(x.luggage_count??'-')}</span><span>旅行社：${esc(x.agency_name||'-')}</span><span>原文：${esc(x.raw_text||'-')}</span><p>${esc(x.remark||'')}</p></div></td></tr>`}
function renderPending(){let html='';for(const x of pendingRows()){const k=keyOf(x),edit=state.editing===k;html+=`<tr class="row ${state.selected.has(k)?'active':''}" onclick="toggleRow('${k}')"><td onclick="event.stopPropagation()"><input type="checkbox" ${state.selected.has(k)?'checked':''} onchange="toggleRow('${k}')"></td><td><b>${esc(fmtOid(x))}</b></td><td>${edit?editInput(x,'order_date','date')+'<br>'+editInput(x,'start_time','time'):`${esc(x.order_date||'-')}<br><span class="muted">${esc(x.start_time||'-')}</span>`}</td><td>${edit?editInput(x,'end_date','date')+'<br>'+editInput(x,'end_time','time'):`${esc(x.end_date||x.order_date||'-')}<br><span class="muted">${esc(x.end_time||'-')}</span>`}</td><td>${edit?editInput(x,'pickup_location')+'<br>'+editInput(x,'dropoff_location'):`<span class="ellipsis">${esc(route(x))}</span>`}</td><td>${edit?editInput(x,'order_type'):esc(x.order_type||'-')}</td><td>${edit?editInput(x,'vehicle_type'):esc(x.vehicle_type||'-')}</td><td>${edit?editInput(x,'price','number'):esc(x.price??'-')}</td><td>${edit?`<textarea class="remark-input" data-row="${k}" data-key="remark" onclick="event.stopPropagation()" onchange="editCell(this)">${esc(x.remark??'')}</textarea>`:`<span class="ellipsis">${esc(brief(x))}</span>`}</td><td class="op" onclick="event.stopPropagation()">${edit?`<button class="link-btn" onclick="saveEdit('${k}')">保存</button><button class="link-btn" onclick="cancelEdit()">取消</button>`:`<button class="link-btn" onclick="toggleExpand('${k}')">${state.expanded.has(k)?'收起':'展开'}</button><button class="link-btn" onclick="confirmOne('${k}')">确认</button><button class="link-btn" onclick="startEdit('${k}')">编辑</button>`}</td></tr>`;if(state.expanded.has(k))html+=detailRow(x)}$('pendingRows').innerHTML=html||'<tr><td colspan="10" style="text-align:center;color:#98a2b3;padding:24px">暂无待确认订单</td></tr>';$('selectedHint').textContent=`已选择 ${selectedRows().length} 单`;renderPreview()}
function toggleRow(k){state.selected.has(k)?state.selected.delete(k):state.selected.add(k);renderPending()}function selectAllPending(){pendingRows().forEach(x=>state.selected.add(keyOf(x)));renderPending()}function clearSelected(){state.selected.clear();renderPending()}function toggleExpand(k){state.expanded.has(k)?state.expanded.delete(k):state.expanded.add(k);renderPending()}function startEdit(k){state.editing=k;renderPending()}function cancelEdit(){state.editing=null;loadAll()}function editCell(i){const r=findPending(i.dataset.row);if(r)r[i.dataset.key]=i.value}
async function saveEdit(k){const x=findPending(k);if(!x)return;if(x.kind==='draft')await api(`/api/parser/drafts/${x.id}`,{method:'PUT',body:JSON.stringify(payload(x))});else await api(`/api/orders/${x.id}`,{method:'PUT',body:JSON.stringify(payload(x))});state.editing=null;toast('已保存');await loadAll()}
async function confirmOne(k){const x=findPending(k);if(!x)return;if(x.kind==='draft')await api(`/api/parser/drafts/${x.id}/confirm`,{method:'POST'});toast('已确认');await loadAll()}async function confirmSelected(){for(const x of selectedRows()){if(x.kind==='draft')await api(`/api/parser/drafts/${x.id}/confirm`,{method:'POST'})}state.selected.clear();toast('已原地确认');await loadAll()}
function renderDrivers(){$('driverList').innerHTML=state.drivers.map(d=>`<div class="pick-card ${state.driver===d.id?'active':''}" onclick="state.driver=${d.id};renderDrivers();renderPreview()"><b>${esc(d.name)}</b><small>${esc(d.phone||'')} · ${esc(d.status)}</small></div>`).join('')||'<div class="hint">无可用司机</div>'}function renderVehicles(){$('vehicleList').innerHTML=state.vehicles.map(v=>`<div class="pick-card ${state.vehicle===v.id?'active':''}" onclick="state.vehicle=${v.id};renderVehicles();renderPreview()"><b>${esc(v.plate_number)}</b><small>${esc(v.vehicle_type||'')} · ${esc(v.seat_count||'')}座</small></div>`).join('')||'<div class="hint">无可用车辆</div>'}
function selectedRows(){return pendingRows().filter(x=>state.selected.has(keyOf(x)))}function renderPreview(){const rows=selectedRows(),driver=state.drivers.find(d=>d.id===state.driver),vehicle=state.vehicles.find(v=>v.id===state.vehicle),total=rows.reduce((s,x)=>s+(Number(x.price)||0),0);$('orderChips').innerHTML=rows.map(x=>`<span class="chip">${esc(fmtOid(x))}</span>`).join('')||'<span class="hint">点击待确认订单勾选</span>';$('assignPreview').innerHTML=rows.length&&driver&&vehicle?`<p>订单：${rows.map(x=>esc(fmtOid(x))).join(', ')}</p><p>司机：${esc(driver.name)}</p><p>车辆：${esc(vehicle.plate_number)}</p><p>预计收入：¥${total}</p>`:'请选择订单、司机、车辆'}
async function assignSelected(){const rows=selectedRows();if(!rows.length)return toast('请先选择订单');if(!state.driver||!state.vehicle)return toast('请先选择司机和车辆');try{const ids=[];for(const x of rows){if(x.kind==='draft'){await api(`/api/parser/drafts/${x.id}`,{method:'PUT',body:JSON.stringify(payload(x))});const r=await api(`/api/parser/drafts/${x.id}/confirm`,{method:'POST'});ids.push(r.order_id)}else{await api(`/api/orders/${x.id}`,{method:'PUT',body:JSON.stringify(payload(x))});ids.push(x.id)}}const res=await api('/api/dispatch/assign',{method:'POST',body:JSON.stringify({order_ids:ids,driver_id:state.driver,vehicle_id:state.vehicle})});if(res.success===false)throw new Error('时间冲突，未派单');state.selected.clear();toast('分配成功，司机端已同步');await loadAll()}catch(e){toast(e.message)}}
function renderAssigned(){$('assignedRows').innerHTML=state.assignments.map(x=>`<tr><td><b>${esc(fmtOid(x))}</b></td><td>${esc(x.order_date||'-')} ${esc(x.start_time||'')}</td><td>${esc(x.end_date||x.order_date||'-')} ${esc(x.end_time||'')}</td><td>${esc(route(x))}</td><td>${esc(x.order_type||'-')}</td><td>${esc(x.order_vehicle_type||x.assigned_vehicle_type||'-')}</td><td>${esc(x.driver_name||'-')}</td><td>${esc(x.plate_number||'-')}</td><td>${esc(x.price??'-')}</td><td><span class="muted">${esc(x.execution_status||x.status||'-')}</span></td><td>${esc(x.remark||'')}</td></tr>`).join('')||'<tr><td colspan="11" style="text-align:center;color:#98a2b3;padding:24px">暂无已分配订单</td></tr>'}
function renderCalendarStatus(){const assigned=state.assignments.length,unassigned=state.orders.length,completed=state.assignments.filter(x=>['completed','returned'].includes(x.execution_status)).length,settled=state.assignments.filter(x=>['settled','paid'].includes(x.settlement_status)).length,unsettled=state.assignments.filter(x=>!['settled','paid'].includes(x.settlement_status)).length,total=assigned+unassigned;const chips=[['s-unassigned','未派车',unassigned],['s-assigned','已派车',assigned],['s-completed','已完成',completed],['s-unsettled','未结账',unsettled],['s-settled','已结账',settled],['s-all','全部',total]];$('calendarStatus').innerHTML=chips.map(x=>`<div class="status-chip ${x[0]}">${x[1]}<b>${x[2]}</b></div>`).join('')}
function colorClass(x){if(['completed','returned'].includes(x.execution_status))return 'c-completed';if(['settled','paid'].includes(x.settlement_status))return 'c-settled';if(!['settled','paid'].includes(x.settlement_status))return 'c-unsettled';return 'c-assigned'}
function renderCalendar(){const cols=state.view==='day'?24:(state.view==='week'?7:30),dates=[...Array(cols)].map((_,i)=>dadd($('baseDate').value,i)),gridCols=`180px repeat(${cols}, 1fr)`;let html=`<div class="time-head" style="grid-template-columns:${gridCols}"><div class="head-cell">车辆</div>`+dates.map((d,i)=>`<div class="head-cell">${state.view==='day'?String(i).padStart(2,'0')+':00':d.slice(5)}</div>`).join('')+'</div>';for(const v of state.vehicles){const items=state.calendar.filter(x=>x.vehicle_id===v.id);html+=`<div class="vehicle-row" style="grid-template-columns:${gridCols};min-height:${Math.max(78,items.length*44+22)}px"><div class="vehicle-name">${esc(v.plate_number)}<small>${esc(v.vehicle_type||'')}</small></div>`+dates.map(()=>'<div class="slot"></div>').join('');items.forEach((x,i)=>{let left=180,width=90,label='';if(state.view==='day'){const s=minutes(x.start_time)??0,e=minutes(x.end_time)??1440;left=180+s/1440*1040;width=Math.max(80,(Math.max(e,s+60)-s)/1440*1040);label=`${x.start_time||''}-${x.end_time||''}`}else{const si=Math.max(0,dates.indexOf(x.order_date)),ei=Math.max(si,dates.indexOf(x.end_date||x.order_date));left=180+si/cols*1040;width=Math.max(90,(ei-si+1)/cols*1040);label=x.order_date===(x.end_date||x.order_date)?x.order_date:`${x.order_date} -> ${x.end_date}`}html+=`<div class="eventbar ${colorClass(x)}" style="left:${left}px;width:${width}px;top:${10+i*44}px"><b>${esc(fmtOid(x))} ${esc(label)}</b><small>${esc(route(x))}</small></div>`});html+='</div>'}$('calendarGrid').innerHTML=html}
async function parseBatch(){const lines=$('batchText').value.split(/\\n+/).map(x=>x.trim()).filter(Boolean);if(!lines.length)return toast('先粘贴订单文本');for(const text of lines){await api('/api/parser/text',{method:'POST',body:JSON.stringify({text})})}$('batchText').value='';toast(`已解析 ${lines.length} 条`);await loadAll()}
$('baseDate').value=today();setView('day');
</script>
</body>
</html>"""
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_dashboard_page(self) -> None:
        html = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>调度派单台</title>
  <style>
    :root{--primary:#2563eb;--success:#16a34a;--warning:#f59e0b;--danger:#ef4444;--info:#0891b2;--bg:#f6f8fb;--card:#fff;--line:#dfe7f2;--text:#0f172a;--muted:#64748b;--shadow:0 12px 30px rgba(15,23,42,.08);--r:12px}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 Inter,Arial,"Microsoft YaHei",sans-serif}.app{display:flex;min-height:100vh}.side{width:210px;background:#0f172a;color:#e2e8f0;padding:22px 16px;position:sticky;top:0;height:100vh}.brand{font-size:22px;font-weight:900;letter-spacing:.02em;margin:4px 4px 28px}.nav a{display:flex;align-items:center;gap:10px;color:#cbd5e1;text-decoration:none;padding:11px 12px;border-radius:10px;margin:5px 0;font-weight:700}.nav a:hover,.nav a.active{background:#1e293b;color:#fff}.main{flex:1;padding:24px 28px 44px;max-width:1680px}.top{display:flex;align-items:flex-end;justify-content:space-between;margin-bottom:18px}.eyebrow{color:var(--muted);font-weight:700}.title{font-size:30px;font-weight:900;margin:3px 0}.date-pill{background:#fff;border:1px solid var(--line);border-radius:999px;padding:9px 14px;color:#334155;box-shadow:0 3px 12px rgba(15,23,42,.04)}
    .kpis{display:grid;grid-template-columns:repeat(7,minmax(130px,1fr));gap:14px;margin-bottom:18px}.kpi{background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:16px;box-shadow:var(--shadow);min-height:112px}.kpi .label{color:var(--muted);font-weight:800}.kpi .value{font-size:34px;font-weight:900;margin-top:10px}.kpi .bar{height:4px;border-radius:6px;margin-top:10px;background:#e2e8f0}.primary .bar{background:var(--primary)}.success .bar{background:var(--success)}.warning .bar{background:var(--warning)}.danger .bar{background:var(--danger)}.info .bar{background:var(--info)}
    .section{background:var(--card);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow);margin-bottom:16px;overflow:hidden}.section-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px 18px;border-bottom:1px solid #edf2f7}.section-title{display:flex;align-items:center;gap:10px;font-size:18px;font-weight:900}.step{display:inline-grid;place-items:center;width:24px;height:24px;border-radius:999px;background:#dbeafe;color:#1d4ed8;font-size:13px}.tools{display:flex;align-items:center;gap:9px;flex-wrap:wrap}.body{padding:16px 18px}.btn{height:36px;border:0;border-radius:9px;padding:0 14px;background:var(--primary);color:white;font-weight:900;cursor:pointer}.btn.secondary{background:#f8fafc;color:#334155;border:1px solid var(--line)}.btn.success{background:var(--success)}.btn.warning{background:var(--warning)}.input,.select,.textarea{border:1px solid var(--line);border-radius:9px;background:white;color:#172033}.input,.select{height:36px;padding:0 10px}.textarea{width:100%;min-height:96px;padding:12px;resize:vertical}.hidden{display:none}.muted{color:var(--muted)}.grid-2{display:grid;grid-template-columns:1.2fr .8fr;gap:16px}.grid-4{display:grid;grid-template-columns:1fr 1fr 42px 1fr .95fr;gap:14px}.card{border:1px solid var(--line);border-radius:12px;background:#fbfdff;padding:14px}.card h3{margin:0 0 10px;font-size:15px}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:10px}.compact{max-height:312px}.assigned-wrap{max-height:260px}table{width:100%;border-collapse:separate;border-spacing:0;min-width:1080px}th{position:sticky;top:0;background:#f8fafc;color:#475569;text-align:left;font-size:12px;font-weight:900;padding:10px;border-bottom:1px solid var(--line)}td{height:48px;padding:9px 10px;border-bottom:1px solid #edf2f7;vertical-align:middle}.selected{background:#eff6ff}.ellipsis{display:block;max-width:260px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.link{border:0;background:transparent;color:#2563eb;font-weight:900;padding:0 5px;cursor:pointer}.edit{width:100%;height:30px;border:1px solid var(--line);border-radius:7px;padding:0 7px}.badge{display:inline-flex;align-items:center;border-radius:999px;padding:3px 9px;font-size:12px;font-weight:900}.b-assigned{background:#dbeafe;color:#1d4ed8}.b-confirmed{background:#e0f2fe;color:#0369a1}.b-departed{background:#fef3c7;color:#92400e}.b-arrived{background:#ecfeff;color:#0e7490}.b-in_service{background:#f5f3ff;color:#6d28d9}.b-completed,.b-returned{background:#dcfce7;color:#15803d}.b-failed{background:#fee2e2;color:#b91c1c}.b-pending{background:#f1f5f9;color:#475569}.detail td{height:auto;background:#fbfdff}.detail-box{display:grid;grid-template-columns:repeat(4,minmax(160px,1fr));gap:8px}.detail-box p{grid-column:1/-1;margin:0}.pick-list{display:grid;gap:8px;max-height:250px;overflow:auto}.pick{border:1px solid var(--line);border-radius:10px;background:white;padding:10px;cursor:pointer}.pick.active{border-color:var(--success);background:#f0fdf4;box-shadow:0 0 0 3px rgba(22,163,74,.12)}.chips{display:flex;gap:8px;flex-wrap:wrap}.chip{background:#eff6ff;border:1px solid #bfdbfe;color:#1d4ed8;border-radius:8px;padding:7px 9px;font-weight:800}.arrow{display:grid;place-items:center;color:var(--primary);font-size:26px}.preview{background:linear-gradient(135deg,#f0fdf4,#fff)}.status-row{display:flex;gap:9px;flex-wrap:wrap}.status-chip{border:1px solid;border-radius:10px;padding:7px 12px;font-weight:900}.s-unassigned{color:#d97706;background:#fffbeb}.s-assigned{color:#2563eb;background:#eff6ff}.s-completed{color:#16a34a;background:#f0fdf4}.s-unsettled{color:#ef4444;background:#fef2f2}.s-settled{color:#7c3aed;background:#f5f3ff}.tabs{display:flex;border:1px solid var(--line);border-radius:10px;overflow:hidden}.tabs button{height:36px;border:0;border-right:1px solid var(--line);background:white;color:#334155;padding:0 14px;font-weight:900}.tabs button.active{background:var(--primary);color:white}.calendar{overflow:auto;border:1px solid var(--line);border-radius:12px;background:white}.cal-head,.vehicle-row{display:grid;min-width:1220px}.cal-head{position:sticky;top:0;z-index:4;background:#fff;border-bottom:1px solid var(--line)}.head-cell{padding:10px;text-align:center;border-right:1px solid #edf2f7;color:#475569;font-weight:800}.vehicle-name{position:sticky;left:0;z-index:2;background:#fbfdff;border-right:1px solid var(--line);padding:12px;font-weight:900}.vehicle-name small{display:block;color:var(--muted);font-weight:600}.vehicle-row{position:relative;min-height:84px;border-bottom:1px solid #edf2f7}.slot{border-right:1px solid #edf2f7}.event{position:absolute;border:1px solid;border-radius:9px;padding:6px 8px;min-height:40px;font-size:12px;overflow:hidden;background:#eff6ff;border-color:#93c5fd;color:#1d4ed8}.event.completed{background:#f0fdf4;border-color:#86efac;color:#15803d}.event.unsettled{background:#fff7ed;border-color:#fdba74;color:#c2410c}.driver-hero{display:grid;grid-template-columns:1fr 1fr;gap:16px}.action-btn{width:100%;height:50px;border-radius:12px;background:var(--success);color:white;border:0;font-size:16px;font-weight:900}.toast{position:fixed;right:24px;bottom:24px;background:#0f172a;color:#fff;border-radius:12px;padding:12px 16px;display:none}.main{min-width:0;overflow:hidden}.kpis{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}@media(max-width:1180px){.side{width:86px}.brand{font-size:18px;text-align:center}.nav a{justify-content:center}.nav span{display:none}.kpis{grid-template-columns:repeat(2,1fr)}.grid-2,.grid-4,.driver-hero{grid-template-columns:1fr}.arrow{display:none}.main{padding:16px}}
  </style>
</head>
<body>
<div class="app">
  <aside class="side"><div class="brand">调度<br>派单台</div><nav class="nav"><a href="#dashboard" class="active">● <span>总览</span></a><a href="#parser">● <span>解析</span></a><a href="#dispatch">● <span>派车</span></a><a href="#calendar">● <span>日历</span></a><a href="#driver">● <span>司机</span></a></nav></aside>
  <main class="main">
    <div class="top" id="dashboard"><div><div class="eyebrow">WX Dispatch MVP</div><div class="title">运营总览</div></div><div class="date-pill" id="todayText">-</div></div>
    <div class="kpis" id="kpis"></div>
    <section class="section" id="parser"><div class="section-head"><div class="section-title"><span class="step">1</span>订单解析</div><div class="tools"><button class="btn secondary" onclick="toggleParse()">展开/收起</button><button class="btn secondary" onclick="loadAll()">刷新</button></div></div><div class="body hidden" id="parseBox"><textarea class="textarea" id="batchText" placeholder="粘贴订单文本，每行一单：5/24 08:20 京都送机关西 3代 绿800"></textarea><div class="tools" style="margin-top:10px"><button class="btn" onclick="parseBatch()">解析草稿</button><span class="muted">不做聊天 UI，解析后进入待确认订单表。</span></div></div></section>
    <section class="section" id="pending"><div class="section-head"><div class="section-title"><span class="step">2</span>待确认订单</div><div class="tools"><input class="input" type="date"><input class="input" type="date"><input class="input" placeholder="订单号/客户/手机号"><select class="select"><option>全部状态</option><option>parsed</option><option>failed</option></select><button class="btn success" onclick="assignSelected()">一键排单</button><button class="btn warning" onclick="confirmSelected()">原地确认</button></div></div><div class="body"><div class="tools" style="margin-bottom:10px"><button class="btn secondary" onclick="selectAllPending()">全选</button><button class="btn secondary" onclick="clearSelected()">清空选择</button><span class="muted" id="selectedHint">已选择 0 单</span></div><div class="table-wrap compact"><table><thead><tr><th>选择</th><th>编号</th><th>开始日期/时间</th><th>结束日期/时间</th><th>路线</th><th>类型</th><th>车型</th><th>价格</th><th>备注</th><th>操作</th></tr></thead><tbody id="pendingRows"></tbody></table></div></div></section>
    <section class="section" id="dispatch"><div class="section-head"><div class="section-title"><span class="step">3</span>分配资源</div><span class="muted">选订单、司机、车辆后确认分配</span></div><div class="body grid-4"><div class="card"><h3>订单选择</h3><div class="chips" id="orderChips"></div></div><div class="card"><h3>选择司机</h3><div class="pick-list" id="driverList"></div></div><div class="arrow">→</div><div class="card"><h3>选择车辆</h3><div class="pick-list" id="vehicleList"></div></div><div class="card preview"><h3>分配预览</h3><div id="assignPreview" class="muted">请选择订单、司机、车辆</div><button class="btn success" style="width:100%;margin-top:12px" onclick="assignSelected()">确认分配</button></div></div></section>
    <section class="section" id="assigned"><div class="section-head"><div class="section-title"><span class="step">4</span>已分配订单池</div><div class="tools"><input class="input" type="date"><input class="input" placeholder="搜索订单号/客户"><button class="btn secondary">导出</button></div></div><div class="body"><div class="table-wrap assigned-wrap"><table><thead><tr><th>编号</th><th>开始日期/时间</th><th>结束日期/时间</th><th>路线</th><th>类型</th><th>车型</th><th>司机</th><th>车辆</th><th>价格</th><th>状态</th><th>备注</th></tr></thead><tbody id="assignedRows"></tbody></table></div></div></section>
    <section class="section" id="calendar"><div class="section-head"><div class="section-title"><span class="step">5</span>日历排程</div><div class="tools"><div class="tabs"><button id="tab-day" onclick="setView('day')">24h</button><button id="tab-week" onclick="setView('week')">7d</button><button id="tab-month" onclick="setView('month')">30d</button></div><input class="input" type="date" id="baseDate" onchange="loadAll()"><select class="select" id="vehicleFilter" onchange="loadAll()"><option value="">全部车辆</option></select></div></div><div class="body"><div class="status-row" id="calendarStatus" style="margin-bottom:12px"></div><div class="calendar"><div id="calendarGrid"></div></div></div></section>
    <section class="section" id="driver"><div class="section-head"><div class="section-title"><span class="step">6</span>司机端预览</div><span class="muted">司机只看自己的订单和下一步动作</span></div><div class="body driver-hero"><div class="card" id="driverCurrent"></div><div class="card"><h3>下一步动作</h3><button class="action-btn">确认 / 出库 / 到达 / 完成</button><p class="muted">真实小程序司机页会按 execution_status 展示下一步按钮。</p></div></div></section>
  </main>
</div>
<div class="toast" id="toast"></div>
<script>
const $=id=>document.getElementById(id);let state={view:'day',selected:new Set(),expanded:new Set(),editing:null,driver:null,vehicle:null,summary:{},drafts:[],orders:[],drivers:[],vehicles:[],assignments:[],calendar:[]};
const api=async(p,o={})=>{const r=await fetch(p,{headers:{'Content-Type':'application/json'},...o});const b=await r.json();if(!r.ok)throw new Error(b.error||r.statusText);return b};const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));const today=()=>new Date().toISOString().slice(0,10);const key=x=>`${x.kind}:${x.id}`;const route=x=>`${x.pickup_location||'-'} -> ${x.dropoff_location||'-'}`;const fmt=x=>String(x.oid||x.id||'').replace(/^20(\\d{6})/,'$1');const badge=s=>`<span class="badge b-${esc(s||'pending')}">${esc(s||'pending')}</span>`;const toast=m=>{const e=$('toast');e.textContent=m;e.style.display='block';setTimeout(()=>e.style.display='none',2400)};const minutes=t=>{if(!t||!t.includes(':'))return null;const a=t.split(':').map(Number);return a[0]*60+a[1]};const dadd=(d,n)=>{const x=new Date(d+'T00:00:00');x.setDate(x.getDate()+n);return x.toISOString().slice(0,10)};
function toggleParse(){$('parseBox').classList.toggle('hidden')}function setView(v){state.view=v;['day','week','month'].forEach(x=>$('tab-'+x).classList.toggle('active',x===v));loadAll()}
async function loadAll(){if(!$('baseDate').value)$('baseDate').value=today();const d=$('baseDate').value,v=$('vehicleFilter').value;const [summary,drafts,orders,drivers,vehicles,assignments,cal]=await Promise.all([api('/api/dashboard/summary'),api('/api/parser/drafts'),api('/api/dispatch/unassigned-orders'),api('/api/dispatch/drivers'),api('/api/dispatch/vehicles'),api('/api/dispatch/assignments'),api('/api/calendar/dispatch?view='+state.view+'&date='+d+(v?'&vehicle_id='+v:''))]);Object.assign(state,{summary,drafts:(drafts.drafts||[]).filter(x=>x.parse_status!=='confirmed').map(x=>({kind:'draft',...x})),orders:(orders.orders||[]).map(x=>({kind:'order',...x})),drivers:drivers.drivers||[],vehicles:vehicles.vehicles||[],assignments:assignments.assignments||[],calendar:cal.items||[]});render()}
function render(){renderKpis();renderOptions();renderPending();renderDrivers();renderVehicles();renderPreview();renderAssigned();renderCalendarStatus();renderCalendar();renderDriver()}
function renderKpis(){const s=state.summary;$('todayText').textContent=s.date||today();const items=[['今日订单',s.today_orders,'primary'],['已派车',s.today_assigned_orders,'success'],['执行中',s.today_in_service_orders,'info'],['已完成',s.today_completed_orders,'success'],['未派车',s.today_unassigned_orders,'warning'],['草稿',s.pending_drafts,'primary'],['未报备',s.unreported_assignments,'danger']];$('kpis').innerHTML=items.map(i=>`<div class="kpi ${i[2]}"><div class="label">${i[0]}</div><div class="value">${i[1]??0}</div><div class="bar"></div></div>`).join('')}
function renderOptions(){const cur=$('vehicleFilter').value;$('vehicleFilter').innerHTML='<option value="">全部车辆</option>'+state.vehicles.map(v=>`<option value="${v.id}">${esc(v.plate_number)}</option>`).join('');$('vehicleFilter').value=cur}
function rows(){return [...state.drafts,...state.orders].sort((a,b)=>String(a.order_date+a.start_time).localeCompare(String(b.order_date+b.start_time)))}function rowBy(k){return rows().find(x=>key(x)===k)}function selected(){return rows().filter(x=>state.selected.has(key(x)))}function brief(x){return String(x.remark||x.raw_text||'').replace(/\\s+/g,' ').slice(0,90)}
function editInput(x,k,t='text'){return `<input class="edit" data-row="${key(x)}" data-key="${k}" type="${t}" value="${esc(x[k]??'')}" onclick="event.stopPropagation()" onchange="editCell(this)">`}function detail(x){return `<tr class="detail"><td colspan="10"><div class="detail-box"><b>完整解析</b><span>客人：${esc(x.guest_name||'-')}</span><span>联系：${esc(x.guest_contact||'-')}</span><span>人数：${esc(x.passenger_count??'-')}</span><span>行李：${esc(x.luggage_count??'-')}</span><span>旅行社：${esc(x.agency_name||'-')}</span><span>原文：${esc(x.raw_text||'-')}</span><p>${esc(x.remark||'')}</p></div></td></tr>`}
function renderPending(){let h='';for(const x of rows()){const k=key(x),e=state.editing===k;h+=`<tr class="${state.selected.has(k)?'selected':''}" onclick="toggleRow('${k}')"><td onclick="event.stopPropagation()"><input type="checkbox" ${state.selected.has(k)?'checked':''} onchange="toggleRow('${k}')"></td><td><b>${esc(fmt(x))}</b></td><td>${e?editInput(x,'order_date','date')+'<br>'+editInput(x,'start_time','time'):`${esc(x.order_date||'-')}<br><span class="muted">${esc(x.start_time||'-')}</span>`}</td><td>${e?editInput(x,'end_date','date')+'<br>'+editInput(x,'end_time','time'):`${esc(x.end_date||x.order_date||'-')}<br><span class="muted">${esc(x.end_time||'-')}</span>`}</td><td>${e?editInput(x,'pickup_location')+'<br>'+editInput(x,'dropoff_location'):`<span class="ellipsis">${esc(route(x))}</span>`}</td><td>${e?editInput(x,'order_type'):esc(x.order_type||'-')}</td><td>${e?editInput(x,'vehicle_type'):esc(x.vehicle_type||'-')}</td><td>${e?editInput(x,'price','number'):esc(x.price??'-')}</td><td>${e?editInput(x,'remark'):`<span class="ellipsis">${esc(brief(x))}</span>`}</td><td onclick="event.stopPropagation()">${e?`<button class="link" onclick="saveEdit('${k}')">保存</button><button class="link" onclick="cancelEdit()">取消</button>`:`<button class="link" onclick="toggleExpand('${k}')">${state.expanded.has(k)?'收起':'展开'}</button><button class="link" onclick="confirmOne('${k}')">确认</button><button class="link" onclick="startEdit('${k}')">编辑</button>`}</td></tr>`;if(state.expanded.has(k))h+=detail(x)}$('pendingRows').innerHTML=h||'<tr><td colspan="10" class="muted" style="text-align:center;padding:24px">暂无待确认订单</td></tr>';$('selectedHint').textContent=`已选择 ${selected().length} 单`;renderPreview()}
function toggleRow(k){state.selected.has(k)?state.selected.delete(k):state.selected.add(k);renderPending()}function selectAllPending(){rows().forEach(x=>state.selected.add(key(x)));renderPending()}function clearSelected(){state.selected.clear();renderPending()}function toggleExpand(k){state.expanded.has(k)?state.expanded.delete(k):state.expanded.add(k);renderPending()}function startEdit(k){state.editing=k;renderPending()}function cancelEdit(){state.editing=null;loadAll()}function editCell(i){const r=rowBy(i.dataset.row);if(r)r[i.dataset.key]=i.value}function payload(x){return {oid:x.oid,order_date:x.order_date,end_date:x.end_date,start_time:x.start_time,end_time:x.end_time,pickup_location:x.pickup_location,dropoff_location:x.dropoff_location,order_type:x.order_type,vehicle_type:x.vehicle_type,price:x.price,remark:x.remark}}
async function saveEdit(k){const x=rowBy(k);if(x.kind==='draft')await api(`/api/parser/drafts/${x.id}`,{method:'PUT',body:JSON.stringify(payload(x))});else await api(`/api/orders/${x.id}`,{method:'PUT',body:JSON.stringify(payload(x))});state.editing=null;toast('已保存');loadAll()}async function confirmOne(k){const x=rowBy(k);if(x.kind==='draft')await api(`/api/parser/drafts/${x.id}/confirm`,{method:'POST'});toast('已确认');loadAll()}async function confirmSelected(){for(const x of selected()){if(x.kind==='draft')await api(`/api/parser/drafts/${x.id}/confirm`,{method:'POST'})}state.selected.clear();toast('已原地确认');loadAll()}
function renderDrivers(){$('driverList').innerHTML=state.drivers.map(d=>`<div class="pick ${state.driver===d.id?'active':''}" onclick="state.driver=${d.id};renderDrivers();renderPreview()"><b>${esc(d.name)}</b><div class="muted">${esc(d.phone||'')} · ${esc(d.status)}</div></div>`).join('')}function renderVehicles(){$('vehicleList').innerHTML=state.vehicles.map(v=>`<div class="pick ${state.vehicle===v.id?'active':''}" onclick="state.vehicle=${v.id};renderVehicles();renderPreview()"><b>${esc(v.plate_number)}</b><div class="muted">${esc(v.vehicle_type||'')} · ${esc(v.seat_count||'')}座</div></div>`).join('')}
function renderPreview(){const rs=selected(),d=state.drivers.find(x=>x.id===state.driver),v=state.vehicles.find(x=>x.id===state.vehicle);$('orderChips').innerHTML=rs.map(x=>`<span class="chip">${esc(fmt(x))}</span>`).join('')||'<span class="muted">点击待确认订单勾选</span>';$('assignPreview').innerHTML=rs.length&&d&&v?`订单：${rs.map(fmt).join(', ')}<br>司机：${esc(d.name)}<br>车辆：${esc(v.plate_number)}<br>预计收入：¥${rs.reduce((s,x)=>s+(Number(x.price)||0),0)}`:'请选择订单、司机、车辆'}
async function assignSelected(){const rs=selected();if(!rs.length||!state.driver||!state.vehicle)return toast('请选择订单、司机、车辆');const ids=[];for(const x of rs){if(x.kind==='draft'){await api(`/api/parser/drafts/${x.id}`,{method:'PUT',body:JSON.stringify(payload(x))});const r=await api(`/api/parser/drafts/${x.id}/confirm`,{method:'POST'});ids.push(r.order_id)}else ids.push(x.id)}const r=await api('/api/dispatch/assign',{method:'POST',body:JSON.stringify({order_ids:ids,driver_id:state.driver,vehicle_id:state.vehicle})});if(r.success===false)return toast('存在时间冲突，未派单');state.selected.clear();toast('派单成功');loadAll()}
function renderAssigned(){$('assignedRows').innerHTML=state.assignments.map(x=>`<tr><td><b>${esc(fmt(x))}</b></td><td>${esc(x.order_date||'-')} ${esc(x.start_time||'')}</td><td>${esc(x.end_date||x.order_date||'-')} ${esc(x.end_time||'')}</td><td>${esc(route(x))}</td><td>${esc(x.order_type||'-')}</td><td>${esc(x.order_vehicle_type||x.assigned_vehicle_type||'-')}</td><td>${esc(x.driver_name||'-')}</td><td>${esc(x.plate_number||'-')}</td><td>${esc(x.price??'-')}</td><td>${badge(x.execution_status||x.status)}</td><td><span class="ellipsis">${esc(x.remark||'')}</span></td></tr>`).join('')}
function renderCalendarStatus(){const a=state.assignments.length,u=state.orders.length,c=state.assignments.filter(x=>['completed','returned'].includes(x.execution_status)).length;const chips=[['s-unassigned','未派车',u],['s-assigned','已派车',a],['s-completed','已完成',c],['s-unsettled','未结账',state.assignments.length],['s-settled','已结账',0]];$('calendarStatus').innerHTML=chips.map(x=>`<span class="status-chip ${x[0]}">${x[1]} ${x[2]}</span>`).join('')}
function renderCalendar(){const cols=state.view==='day'?24:(state.view==='week'?7:30),dates=[...Array(cols)].map((_,i)=>dadd($('baseDate').value,i)),grid=`180px repeat(${cols},1fr)`;let h=`<div class="cal-head" style="grid-template-columns:${grid}"><div class="head-cell">车辆</div>`+dates.map((d,i)=>`<div class="head-cell">${state.view==='day'?String(i).padStart(2,'0')+':00':d.slice(5)}</div>`).join('')+'</div>';for(const v of state.vehicles){const items=state.calendar.filter(x=>x.vehicle_id===v.id);h+=`<div class="vehicle-row" style="grid-template-columns:${grid};min-height:${Math.max(84,items.length*46+24)}px"><div class="vehicle-name">${esc(v.plate_number)}<small>${esc(v.vehicle_type||'')}</small></div>`+dates.map(()=>'<div class="slot"></div>').join('');items.forEach((x,i)=>{let left=180,width=90;if(state.view==='day'){const s=minutes(x.start_time)??0,e=minutes(x.end_time)??s+90;left=180+s/1440*1040;width=Math.max(88,(Math.max(e,s+60)-s)/1440*1040)}else{const si=Math.max(0,dates.indexOf(x.order_date)),ei=Math.max(si,dates.indexOf(x.end_date||x.order_date));left=180+si/cols*1040;width=Math.max(88,(ei-si+1)/cols*1040)}h+=`<div class="event ${['completed','returned'].includes(x.execution_status)?'completed':'unsettled'}" style="left:${left}px;width:${width}px;top:${12+i*46}px"><b>${esc(fmt(x))} ${esc(x.start_time||'')}</b><br>${esc(route(x))}</div>`});h+='</div>'}$('calendarGrid').innerHTML=h}
function renderDriver(){const x=state.assignments[0];$('driverCurrent').innerHTML=x?`<h3>当前订单</h3><p><b>${esc(fmt(x))}</b> ${badge(x.execution_status)}</p><p>${esc(x.order_date)} ${esc(x.start_time)}-${esc(x.end_time)}</p><p>${esc(route(x))}</p><p class="muted">司机：${esc(x.driver_name)} · 车辆：${esc(x.plate_number)}</p>`:'<h3>当前订单</h3><p class="muted">暂无订单</p>'}
async function parseBatch(){const lines=$('batchText').value.split(/\\n+/).map(x=>x.trim()).filter(Boolean);for(const text of lines)await api('/api/parser/text',{method:'POST',body:JSON.stringify({text})});$('batchText').value='';toast(`已解析 ${lines.length} 条`);loadAll()}
$('baseDate').value=today();setView('day');
</script>
</body>
</html>"""
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return
