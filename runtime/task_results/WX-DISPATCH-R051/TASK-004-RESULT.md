# TASK-004 验证与回归

## 修改了什么
- 扩展司机 API smoke 验证，检查 fleet latest location 是否包含车辆状态、执行状态、派车状态和当前订单。

## 涉及文件
- `scripts/verify_driver_api.py`
- `runtime/task_results/WX-DISPATCH-R051/`

## 验证方式
- `python -m compileall backend scripts`
- `python scripts/reset_demo_db.py`
- `python scripts/health_check.py`
- `python scripts/verify_driver_api.py`
- `npm.cmd run build`
- `npm.cmd run lint`

## 是否完成
DONE

## 风险
- 需要人工确认调度端 Fleet Map 视觉和刷新频率是否符合现场使用习惯。
