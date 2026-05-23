# TASK-006：R014 回归验证

## 修改了什么
- 完成本轮资源系统结果归档。
- 后端、前端、资源 smoke 均通过验证。

## 涉及文件
- `runtime/task_results/WX-DISPATCH-R014/`

## 验证方式
- `python -m compileall backend scripts`
- `python scripts/verify_resources_api.py`
- `npm.cmd run build`
- `npm.cmd run lint`

## 是否完成
DONE

## 风险
- 本轮未跑完整订单/派车/司机端回归；修改点主要集中在资源模块。
