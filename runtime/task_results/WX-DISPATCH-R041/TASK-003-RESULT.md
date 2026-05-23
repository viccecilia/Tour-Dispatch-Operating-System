# TASK-003 订单详情页司机视角重构

## 修改了什么
- 司机端当前订单卡只显示时间、路线、客人、电话、车辆、车型、备注、状态和操作。
- 保持司机端不展示订单售价、旅行社结算金额、平台利润等财务后台字段。
- 增加电话、导航到上车点、导航到终点按钮。

## 涉及文件
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.js`

## 验证方式
- `node --check miniapp/pages/driver/index.js`
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 司机收入仍依赖后续财务结算规则完善，本轮只保留费用报备入口。
