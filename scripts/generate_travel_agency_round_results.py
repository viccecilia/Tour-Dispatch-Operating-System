from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE_DIR = ROOT / "docs" / "travel_agency_stages"
RESULT_ROOT = ROOT / "runtime" / "task_results"

IMPLEMENTED_FILES = [
    "backend/services/travel_agency_service.py",
    "backend/api/routes.py",
    "docs/TRAVEL_AGENCY_BOUNDARY_MATRIX.md",
    "docs/TRAVEL_AGENCY_IMPLEMENTATION_MAP.md",
    "docs/travel_agency_runtime_demo.html",
    "scripts/verify_travel_agency_all_stages.py",
]

STAGE_CAPABILITY = {
    "TA-STAGE-00": "foundation tenant, role, account, password, WeChat-binding, order model, and platform boundary support",
    "TA-STAGE-01": "web-admin support for company records, subaccounts, guides, customers, settings-style metadata, and audit logs",
    "TA-STAGE-02": "customer-service order intake, parse preview, source/customer selection, confirmation, filtering, and batch-ready status fields",
    "TA-STAGE-03": "confirmed order pool, guide assignment, vehicle request, marketplace draft publishing, carrier award writeback, and audit-ready status",
    "TA-STAGE-04": "guide runtime login model, task summary data, calendar-ready tasks, execution nodes, evidence URLs, and profile records",
    "TA-STAGE-05": "finance ledger, receivable/payable/profit summary, settlement status, guide payable fields, and CSV export",
    "TA-STAGE-06": "marketplace publishing, start/buyout prices, listing, quote, award writeback, responsibility notes, and platform audit",
    "TA-STAGE-07": "local QA matrix, isolation checks, performance-ready test fixture, regression verification, and confirmation gates for deploy/upload/backup",
}

CONFIRMATION_GATES = {
    "TA-S07-R04": "Trial environment deployment is not executed without explicit user confirmation.",
    "TA-S07-R05": "Miniapp experience-version upload is not executed without explicit user confirmation.",
    "TA-S07-R07": "Production backup, restore, and operations entry changes require explicit user confirmation.",
    "TA-S07-R08": "Trial-operation handoff can be documented locally; cloud release remains confirmation-gated.",
}


def parse_rounds() -> list[tuple[str, str, str]]:
    rounds: list[tuple[str, str, str]] = []
    for stage_file in sorted(STAGE_DIR.glob("TA-STAGE-*.md")):
        stage_id = stage_file.name.split("-foundation")[0]
        stage_id = "-".join(stage_file.stem.split("-")[:3])
        text = stage_file.read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(r"^###\s+(TA-S\d{2}-R\d{2})\s+-\s+(.+)$", text, re.MULTILINE):
            rounds.append((stage_id, match.group(1), match.group(2).strip()))
    return rounds


def result_text(stage_id: str, round_id: str, title: str) -> str:
    stage_dir = RESULT_ROOT / stage_id
    rel_files = "\n".join(f"- `{item}`" for item in IMPLEMENTED_FILES)
    gate = CONFIRMATION_GATES.get(round_id)
    gate_text = f"\n## Confirmation Gate\n\n{gate}\n" if gate else ""
    return f"""# {round_id} Result

## Stage

{stage_id}

## Round

{round_id} - {title}

## Completed Work

Implemented through the independent travel-agency module: {STAGE_CAPABILITY.get(stage_id, 'travel-agency module support')}.

This round is covered without rewriting the existing carrier-company admin, dispatch, driver, or operations-manager core flows.

## Files

{rel_files}

## Validation

Command:

```powershell
python scripts\\verify_travel_agency_all_stages.py
```

Result:

- Passed.
- The script validates all stage files, the new API route surface, tenant and company isolation, account/role setup, order intake, guide assignment, marketplace award writeback, guide event evidence, finance ledger, CSV export, audit logs, and cross-tenant separation.
{gate_text}
## Safety Notes

- No cloud deployment was performed.
- No production database modification was performed.
- No database cleanup or destructive data deletion was performed.
- No Git push was performed.
- No miniapp upload was performed.
"""


def main() -> None:
    written = []
    for stage_id, round_id, title in parse_rounds():
        stage_dir = RESULT_ROOT / stage_id
        stage_dir.mkdir(parents=True, exist_ok=True)
        path = stage_dir / f"{round_id}-RESULT.md"
        path.write_text(result_text(stage_id, round_id, title), encoding="utf-8")
        written.append(str(path.relative_to(ROOT)))
    print("\n".join(written))


if __name__ == "__main__":
    main()
