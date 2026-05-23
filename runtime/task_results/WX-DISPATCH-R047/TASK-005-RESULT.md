# TASK-005：验证脚本补充

## 修改了什么
- `scripts/verify_dispatch_api.py` 增加派车到司机端可见、明日订单可见、司机确认后调度端可见的验证。
- `scripts/verify_driver_api.py` 输出 dashboard 新增联动统计。

## 涉及文件
- `scripts/verify_dispatch_api.py`
- `scripts/verify_driver_api.py`

## 验证方式
- `python scripts/verify_dispatch_api.py`
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 验证脚本会创建 smoke 数据；演示前需要执行 `python scripts/reset_demo_db.py` 固定演示库。
