import json
import re
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
TARGETS = [ROOT_DIR / "frontend" / "src", ROOT_DIR / "miniapp"]
UI_ENGLISH_PATTERNS = [
    r"\bDashboard\b",
    r"\bParser\b",
    r"\bOrders\b",
    r"\bDispatch\b",
    r"\bCalendar\b",
    r"\bDriver Monitor\b",
    r"\bVehicles\b",
    r"\bFinance\b",
    r"\bSettings\b",
    r"\bLoading\b",
    r"\bNo notifications\b",
    r"\bMark all read\b",
]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    findings = []
    compiled = [re.compile(pattern) for pattern in UI_ENGLISH_PATTERNS]
    for root in TARGETS:
        for path in root.rglob("*"):
            if path.suffix.lower() not in {".ts", ".tsx", ".js", ".wxml", ".json"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for index, line in enumerate(text.splitlines(), 1):
                normalized_path = str(path.relative_to(ROOT_DIR)).replace("\\", "/")
                if normalized_path.endswith("i18n/dictionaries.ts") or normalized_path.endswith("miniapp/utils/i18n.js"):
                    continue
                if line.strip().startswith("import ") or " from \"" in line or " from '" in line:
                    continue
                for pattern in compiled:
                    if pattern.search(line):
                        findings.append(
                            {
                                "file": normalized_path,
                                "line": index,
                                "pattern": pattern.pattern,
                                "text": line.strip()[:160],
                            }
                        )
                        break
    print(json.dumps({"finding_count": len(findings), "findings": findings[:80]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
