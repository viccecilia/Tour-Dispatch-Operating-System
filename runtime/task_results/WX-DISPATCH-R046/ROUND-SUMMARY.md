# WX-DISPATCH-R046 总结

## Round Name
Driver UX Polish & Real Map Integration

## 完成内容
- 司机端 UI 收紧，卡片层级、间距、字号和按钮更偏移动端 App。
- 顶部 Driver Hero 更突出，显示司机、在线状态、车辆、日期时间和状态。
- 下一步主动作改为底部固定大按钮。
- 微信 map 组件绑定当前位置、上车点、终点 markers。
- 获取当前位置后刷新地图中心。
- `wx.openLocation` 仅在订单目的地有坐标时调用。
- 无坐标时提供 Google Maps URL fallback 并复制到剪贴板。
- 任务地图页继续保持当前订单展开、后续订单折叠。
- 新增 `docs/DRIVER_UI_GUIDELINES.md`。
- 司机端不显示订单销售价格。

## 验证结果
- `python -m compileall backend scripts`：通过。
- `python scripts/reset_demo_db.py`：通过。
- `python scripts/health_check.py`：通过。
- `$env:PYTHONIOENCODING='utf-8'; python scripts/verify_driver_api.py`：通过。
- `python scripts/verify_dispatch_api.py`：通过。
- `node --check miniapp/pages/driver/index.js`：通过。

## 未完成/风险
- 未接复杂实时轨迹。
- 未接 Google Maps JS SDK。
- 订单如果没有坐标，上车点/终点 marker 不会显示，只提供文字地址和 Google Maps URL fallback。
- 需要真机确认微信定位权限、openLocation 和按钮手感。
