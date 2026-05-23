# TASK-002：Web 页面 Playwright 截图

## 修改了什么
- 新增 `scripts/capture_web_snapshots.py`。
- 自动登录 React Console。
- 自动截图 Dashboard、Dispatch、Calendar、Driver Monitor、Finance、Analytics、Automation、Settings。

## 涉及文件
- `scripts/capture_web_snapshots.py`
- `docs/ui_snapshots/R055/web-dashboard.png`
- `docs/ui_snapshots/R055/web-dispatch.png`
- `docs/ui_snapshots/R055/web-calendar.png`
- `docs/ui_snapshots/R055/web-driver-monitor.png`
- `docs/ui_snapshots/R055/web-finance.png`
- `docs/ui_snapshots/R055/web-analytics.png`
- `docs/ui_snapshots/R055/web-automation.png`
- `docs/ui_snapshots/R055/web-settings.png`

## 验证方式
- `python scripts/capture_web_snapshots.py`
- 人工打开 `web-dashboard.png` 确认不是登录页

## 是否完成
DONE

## 风险
- 脚本依赖前端 `http://127.0.0.1:5173` 和后端 `http://127.0.0.1:18765` 已启动。
