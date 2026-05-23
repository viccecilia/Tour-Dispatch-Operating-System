# TASK-005：验证脚本与回归

## 修改了什么
- `scripts/verify_driver_api.py` 增加车辆状态流验证。
- `scripts/verify_dispatch_api.py` 增加 dashboard 车辆状态统计输出。

## 涉及文件
- `scripts/verify_driver_api.py`
- `scripts/verify_dispatch_api.py`

## 验证方式
- `python -m compileall backend scripts`
- `python scripts/reset_demo_db.py`
- `python scripts/health_check.py`
- `python scripts/verify_driver_api.py`
- `python scripts/verify_dispatch_api.py`
- `cd frontend && npm run build`
- `cd frontend && npm run lint`

## 是否完成
DONE

## 风险
- 验证脚本会产生 smoke 数据；演示前应执行 `python scripts/reset_demo_db.py`。
