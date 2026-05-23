import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FEEDBACK_DIR = ROOT / "runtime" / "pilot_feedback" / "R068"
INPUT = FEEDBACK_DIR / "feedback_items.json"
OUTPUT = FEEDBACK_DIR / "PILOT_IMPROVEMENT_QUEUE.md"

PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def load_items() -> list[dict]:
    if not INPUT.exists():
        FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
        INPUT.write_text("[]\n", encoding="utf-8")
    return json.loads(INPUT.read_text(encoding="utf-8"))


def render(items: list[dict]) -> str:
    sorted_items = sorted(items, key=lambda item: (PRIORITY_ORDER.get(item.get("priority", "P3"), 9), item.get("id", "")))
    priority_counts = Counter(item.get("priority", "P3") for item in sorted_items)
    status_counts = Counter(item.get("status", "new") for item in sorted_items)
    role_counts = Counter(item.get("role", "unknown") for item in sorted_items)

    lines = [
        "# R068 Pilot Improvement Queue",
        "",
        "## Summary",
        "",
        f"- Total: {len(sorted_items)}",
        f"- P0: {priority_counts.get('P0', 0)}",
        f"- P1: {priority_counts.get('P1', 0)}",
        f"- P2: {priority_counts.get('P2', 0)}",
        f"- P3: {priority_counts.get('P3', 0)}",
        "",
        "## By Status",
        "",
    ]
    for status, count in sorted(status_counts.items()):
        lines.append(f"- {status}: {count}")
    lines.extend(["", "## By Role", ""])
    for role, count in sorted(role_counts.items()):
        lines.append(f"- {role}: {count}")

    lines.extend([
        "",
        "## Queue",
        "",
        "| ID | Priority | Role | Area | Issue | Expected | Status | Next Action |",
        "|---|---|---|---|---|---|---|---|",
    ])
    for item in sorted_items:
        lines.append(
            "| {id} | {priority} | {role} | {area} | {issue} | {expected} | {status} | {next_action} |".format(
                id=item.get("id", "-"),
                priority=item.get("priority", "-"),
                role=item.get("role", "-"),
                area=item.get("area", "-"),
                issue=str(item.get("issue", "-")).replace("|", "/"),
                expected=str(item.get("expected", "-")).replace("|", "/"),
                status=item.get("status", "-"),
                next_action=str(item.get("next_action", "-")).replace("|", "/"),
            )
        )
    lines.extend([
        "",
        "## Usage",
        "",
        "Edit `runtime/pilot_feedback/R068/feedback_items.json`, then run:",
        "",
        "```bash",
        "python scripts/generate_pilot_feedback_queue.py",
        "```",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    items = load_items()
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render(items), encoding="utf-8")
    print(json.dumps({"items": len(items), "output": str(OUTPUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
