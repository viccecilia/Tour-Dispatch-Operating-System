import os
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SNAPSHOT_ROUND = os.environ.get("WX_DISPATCH_UI_ROUND", "R055")
SNAPSHOT_DIR = ROOT_DIR / "docs" / "ui_snapshots" / SNAPSHOT_ROUND
REPORT_PATH = SNAPSHOT_DIR / "UI_SNAPSHOT_REPORT.md"

EXPECTED_MINIAPP = [
    "miniapp-driver-home.png",
    "miniapp-driver-yard.png",
    "miniapp-driver-map.png",
    "miniapp-driver-expense.png",
    "miniapp-driver-profile.png",
]

EXPECTED_WEB = [
    "web-dashboard.png",
    "web-dispatch.png",
    "web-calendar.png",
    "web-driver-monitor.png",
    "web-finance.png",
    "web-analytics.png",
    "web-automation.png",
    "web-settings.png",
]

PAGE_NOTES = {
    "web-dashboard.png": "React 管理端总览页。",
    "web-dispatch.png": "调度工作台页面。",
    "web-calendar.png": "派车日历页面。",
    "web-driver-monitor.png": "司机监控页面。",
    "web-finance.png": "财务台账页面。",
    "web-analytics.png": "经营分析页面。",
    "web-automation.png": "自动化规则页面。",
    "web-settings.png": "设置页面。",
    "miniapp-driver-home.png": "司机端首页。",
    "miniapp-driver-yard.png": "司机端出入库页。",
    "miniapp-driver-map.png": "司机端任务地图页。",
    "miniapp-driver-expense.png": "司机端费用页。",
    "miniapp-driver-profile.png": "司机端我的页面。",
}


def status_line(filename: str) -> str:
    path = SNAPSHOT_DIR / filename
    status = "已归档" if path.exists() else "待补充"
    size = f"{path.stat().st_size / 1024:.1f} KB" if path.exists() else "-"
    return f"| `{filename}` | {PAGE_NOTES.get(filename, '-')} | {status} | {size} |"


def main() -> None:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    all_pngs = sorted(path.name for path in SNAPSHOT_DIR.glob("*.png"))
    lines = [
        f"# UI Snapshot Report - {SNAPSHOT_ROUND}",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 截图目录：`docs/ui_snapshots/{SNAPSHOT_ROUND}/`",
        f"- 已发现 PNG：{len(all_pngs)} 个",
        "",
        "## Web 截图",
        "",
        "| 文件 | 页面说明 | 状态 | 大小 |",
        "| --- | --- | --- | --- |",
        *[status_line(filename) for filename in EXPECTED_WEB],
        "",
        "## 小程序截图",
        "",
        "| 文件 | 页面说明 | 状态 | 大小 |",
        "| --- | --- | --- | --- |",
        *[status_line(filename) for filename in EXPECTED_MINIAPP],
        "",
        "## 本轮视觉变化",
        "",
        "- 管理端截图用于观察 Dashboard、Dispatch、Calendar、Driver Monitor、Finance、Analytics、Automation、Settings 的整体视觉变化。",
        "- 小程序截图需要按 `docs/MINIAPP_SCREENSHOT_GUIDE.md` 从微信开发者工具手动补充。",
        "",
        "## 人工备注区",
        "",
        "- 页面是否显得高级：",
        "- 哪些页面仍然空：",
        "- 哪些卡片/表格需要下一轮调整：",
        "",
        "## 未解决视觉问题",
        "",
        "- 待人工填写。",
        "",
        "## 下一轮 UI 建议",
        "",
        "- 待人工填写。",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"generated={REPORT_PATH}")


if __name__ == "__main__":
    main()
