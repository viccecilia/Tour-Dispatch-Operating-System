# WX-DISPATCH-R031 Driver Mobile Experience Upgrade

## 本轮完成内容
- 小程序司机端改为真正移动工作台：今日任务、当前订单、下一步大按钮、弱网暂存、位置上报、导航入口。
- Driver Monitor 改为中文调度监控：任务状态、最新报备、最新位置、在线状态。
- 后端司机 dashboard 的预计收入改为司机工资字段聚合，不暴露订单价格。
- 保留原有司机身份隔离、状态顺序流转、位置日志写入。

## 关键文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`
- `backend/services/driver_service.py`
- `frontend/src/pages/DriverMonitorPage.tsx`

## 验证结果
- 后端编译通过。
- 司机 API 验证通过：状态流转、重复报备拦截、位置日志、最新位置、司机隔离均通过。
- 小程序 JS 语法检查通过。
- React build 通过。
- React lint 通过。

## 风险
- 微信定位和 openLocation 必须用微信开发者工具或真机确认。
- 当前不做复杂地图、轨迹回放、WebSocket。
- demo 数据司机工资大多为空，今日预计收入可能显示 0。
