# WX-DISPATCH-R018：Live Map & Fleet Tracking

## 本轮结果
- 新增 `location_logs` 表。
- 新增司机位置上报 API。
- 司机报备自动写入位置日志。
- 小程序司机端新增“上报当前位置”。
- 新增最新车队位置查询。
- Driver Monitor 显示在线车辆、最新位置和坐标列表。

## 验证结果
- `python -m compileall backend scripts`：通过。
- `python scripts/verify_driver_api.py`：通过。
- `npm.cmd run build`：通过。
- `npm.cmd run lint`：通过。
- 位置 smoke：
  - `location_success: true`
  - `latest_has_driver: true`
  - `driver_log_count: 2`
  - `online_status: online`
- 浏览器检查：
  - “车队位置监控”可见
  - “在线车辆”可见
  - 坐标和测试位置文字可见

## 风险
- 当前是坐标列表/地图占位，不是地图渲染。
- 在线状态基于最近上报时间，不是实时心跳。
- 小程序定位权限需要真机人工确认。

## 下一轮建议
- 接入轻量地图展示，或先用内部地点库坐标做“车辆点位面板”。
- 增加位置上报频率控制，避免司机端频繁请求。
