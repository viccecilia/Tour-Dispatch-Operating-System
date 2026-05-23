# TASK-001：execution_status 统一

## 修改了什么
- 继续沿用 `assignments.execution_status` 与 `orders.execution_status` 的同一状态流：
  - `assigned`
  - `confirmed`
  - `departed`
  - `arrived`
  - `in_service`
  - `completed`
  - `returned`
- 司机报备仍是状态推进的唯一入口，避免调度端和司机端各自改状态导致错乱。

## 涉及文件
- `backend/services/driver_service.py`
- `scripts/verify_driver_api.py`

## 验证方式
- `python scripts/verify_driver_api.py`
- 验证项：`status_flow` 为 `confirmed -> departed -> arrived -> in_service -> completed -> returned`

## 是否完成
DONE

## 风险
- 本轮不新增复杂状态机表，仍以当前 assignment/order 字段为主。
