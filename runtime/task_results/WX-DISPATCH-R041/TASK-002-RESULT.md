# TASK-002 司机每日出车流程状态机

## 修改了什么
- 新增司机工作流事件表与轻量状态写入能力。
- 支持车辆点检、酒精测试、点呼出库、车辆清扫、入库点检、入库酒测、点呼入库等工作流事件。
- Driver Workbench API 返回当前下一步、车辆状态、清扫状态、酒测状态。

## 涉及文件
- `backend/db/schema.sql`
- `backend/db/database.py`
- `backend/services/driver_service.py`
- `backend/api/routes.py`
- `scripts/verify_driver_api.py`

## 验证方式
- `python -m compileall backend scripts`
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 状态机仍是 MVP 级规则，后续可以按真实运营把“点检/酒测/点呼”的强制顺序做得更严格。
