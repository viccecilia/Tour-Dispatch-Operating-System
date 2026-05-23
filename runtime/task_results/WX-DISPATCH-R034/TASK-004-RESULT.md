# TASK-004：验证脚本覆盖

## 修改了什么
- 扩展司机 API 验证脚本，覆盖司机通知生成、读取、标记已读。

## 涉及文件
- `scripts/verify_driver_api.py`

## 验证方式
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 验证脚本依赖本地后端服务运行在 `http://127.0.0.1:18765`。
