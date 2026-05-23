# TASK-001：截图目录规范

## 修改了什么
- 新增统一截图目录 `docs/ui_snapshots/R055/`。
- Web 截图按统一命名保存。
- 小程序截图文件名在报告中预留，等待微信开发者工具手动补充。

## 涉及文件
- `docs/ui_snapshots/R055/`

## 验证方式
- `python scripts/capture_web_snapshots.py`
- `python scripts/generate_ui_snapshot_report.py`

## 是否完成
DONE

## 风险
- 小程序截图需要人工从微信开发者工具补充。
