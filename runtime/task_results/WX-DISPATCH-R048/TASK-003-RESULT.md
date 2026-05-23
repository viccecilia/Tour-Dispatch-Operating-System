# TASK-003：vehicle status 自动变化

## 修改了什么
- 新增车辆运行状态联动：
  - 出库 / 到达：`outbound`
  - 服务中 / 完成：`in_service`
  - 归库：`returned`
- 出入库 workflow 事件也会推动车辆状态：
  - `roll_call_out` -> `outbound`
  - `roll_call_in` -> `returned`
- 取消分配和重新分配时，如果车辆没有其他活动任务，会恢复为 `available`。

## 涉及文件
- `backend/services/driver_service.py`
- `backend/services/dispatch_service.py`
- `scripts/verify_driver_api.py`

## 验证方式
- `python scripts/verify_driver_api.py`
- 验证项：
  - `vehicle_status_after_roll_call_out = outbound`
  - `vehicle_outbound_after_depart = true`
  - `vehicle_in_service_after_start = true`
  - `vehicle_returned_after_return = true`

## 是否完成
DONE

## 风险
- `returned` 是独立状态，不等同 `available`；车辆是否重新投入派车，需要运营端或后续规则确认。
