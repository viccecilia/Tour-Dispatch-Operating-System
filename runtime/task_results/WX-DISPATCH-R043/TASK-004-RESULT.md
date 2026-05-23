# TASK-004 顶部状态卡联动

## 修改了什么
- 顶部司机状态卡优先读取 driver workbench 的 `vehicle_status`。
- 后端车辆状态识别增强：`roll_call_out` 表示已出库，`roll_call_in` / `vehicle_check_in` 表示已入库。
- 验证脚本新增出库/入库 workflow 状态验证。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `backend/services/driver_service.py`
- `scripts/verify_driver_api.py`

## 验证方式
- `python scripts/verify_driver_api.py`
- 验证输出包含：
  - `workbench_after_roll_call_out_vehicle_status: 已出库`
  - `workbench_after_vehicle_status: 已入库`

## 是否完成
DONE

## 风险
- 修改后需要重启后端服务才能让运行中进程加载新逻辑；本轮已重启并验证。
