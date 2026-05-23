# TASK-003：出入库页 Step Flow 化

## 修改了什么
- 新增出库和入库分组 Step 数据。
- 出库按车辆检查、证件确认、健康确认分组。
- 入库按车辆清扫、入库点检、入库确认分组。
- 保留原有检查项点击逻辑和点呼出库/点呼入库动作。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`

## 验证方式
- `node --check miniapp/pages/driver/index.js`
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- Step Flow 的勾选状态仍是本地页面状态，未新增复杂审核或持久化审批。
