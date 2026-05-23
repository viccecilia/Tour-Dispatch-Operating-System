# TASK-001 任务地图页主页面化

## 修改了什么
- 将司机端 `任务地图` 页改为订单执行主页面。
- 当前订单默认展开，显示时间、上车点、终点、客人、电话、车辆和状态。
- 后续订单进入折叠列表，司机可以点击切换。

## 涉及文件
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxss`

## 验证方式
- `node --check miniapp/pages/driver/index.js`
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 需要微信开发者工具人工确认折叠列表在小屏幕上的手感。
