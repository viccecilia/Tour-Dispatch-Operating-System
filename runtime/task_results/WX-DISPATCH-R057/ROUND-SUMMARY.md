# WX-DISPATCH-R057：UI Snapshot Archive & Comparison System

## 修改了什么
- 建立 UI 截图归档目录规范。
- 新增 Web 自动截图脚本。
- 新增小程序截图人工流程文档。
- 新增 UI 截图报告生成脚本。
- 新增 UI Round 归档模板。

## 涉及文件
- `scripts/capture_web_snapshots.py`
- `scripts/generate_ui_snapshot_report.py`
- `docs/MINIAPP_SCREENSHOT_GUIDE.md`
- `docs/UI_ROUND_ARCHIVE_TEMPLATE.md`
- `docs/ui_snapshots/R055/`
- `runtime/task_results/WX-DISPATCH-R057/`

## 验证结果
- `python -m compileall scripts`：通过
- `python scripts/capture_web_snapshots.py`：通过，生成 8 张 Web 截图
- `python scripts/generate_ui_snapshot_report.py`：通过，生成 `UI_SNAPSHOT_REPORT.md`

## 归档文件
- `docs/ui_snapshots/R055/web-dashboard.png`
- `docs/ui_snapshots/R055/web-dispatch.png`
- `docs/ui_snapshots/R055/web-calendar.png`
- `docs/ui_snapshots/R055/web-driver-monitor.png`
- `docs/ui_snapshots/R055/web-finance.png`
- `docs/ui_snapshots/R055/web-analytics.png`
- `docs/ui_snapshots/R055/web-automation.png`
- `docs/ui_snapshots/R055/web-settings.png`

## 是否完成
DONE

## 风险
- 小程序截图仍需通过微信开发者工具人工补充。
- Web 截图脚本依赖前端和后端服务已启动。
