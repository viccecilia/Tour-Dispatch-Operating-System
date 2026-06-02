from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


CHECKS = [
    {
        "name": "stage file declares TA-S00-R01",
        "path": "docs/travel_agency_stages/TA-STAGE-00-foundation.md",
        "needles": ["TA-S00-R01", "Goal:", "Work:", "Acceptance:", "Validation:"],
    },
    {
        "name": "boundary matrix names role surfaces",
        "path": "docs/TRAVEL_AGENCY_BOUNDARY_MATRIX.md",
        "needles": [
            "Travel agency portal",
            "Carrier admin console",
            "Carrier dispatcher console",
            "Carrier operations console",
            "Driver miniapp",
        ],
    },
    {
        "name": "agency portal service carries tenant and agency isolation",
        "path": "backend/services/agency_portal_service.py",
        "needles": [
            '"agency_id"',
            '"tenant_id"',
            "WHERE tenant_id = ?",
            "AND agency_id = ?",
            '"order_source": "agency_portal"',
        ],
    },
    {
        "name": "agency ledger is scoped to current tenant",
        "path": "backend/services/agency_service.py",
        "needles": [
            "get_current_tenant_id()",
            "WHERE tenant_id = ?",
            "AND tenant_id = ?",
            "COALESCE(status, '') != 'deleted'",
        ],
    },
    {
        "name": "frontend exposes agency portal as separate surface",
        "path": "frontend/src/app/App.tsx",
        "needles": [
            'window.location.hash.replace("#", "") === "agency-portal"',
            "<AgencyPortalPage />",
            'page === "finance"',
            'role === "operations_manager"',
        ],
    },
    {
        "name": "sidebar preserves role-based visibility",
        "path": "frontend/src/layouts/SaasShell.tsx",
        "needles": [
            "visibleNavItems",
            'key === "finance"',
            'role === "operations_manager"',
            'role === "dispatcher"',
        ],
    },
    {
        "name": "api routes keep agency portal routes separate",
        "path": "backend/api/routes.py",
        "needles": [
            'path == "/api/agency-portal/agencies"',
            'path == "/api/agency-portal/login"',
            'path == "/api/agency-portal/orders"',
            'self.require_role({"admin", "dispatcher", "operations_manager"})',
        ],
    },
]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="ignore")


def main() -> None:
    results = []
    for check in CHECKS:
        text = read_text(check["path"])
        missing = [needle for needle in check["needles"] if needle not in text]
        results.append(
            {
                "name": check["name"],
                "path": check["path"],
                "ok": not missing,
                "missing": missing,
            }
        )

    failed = [item for item in results if not item["ok"]]
    payload = {
        "ok": not failed,
        "stage": "TA-STAGE-00",
        "round": "TA-S00-R01",
        "checks": results,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
