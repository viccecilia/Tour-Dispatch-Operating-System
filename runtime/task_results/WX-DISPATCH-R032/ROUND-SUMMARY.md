# WX-DISPATCH-R032 Live Driver Map & Fleet Tracking

## 本轮完成内容
- 建立轻量车队位置服务，基于 `location_logs` 读取司机最新位置。
- 新增 `/api/fleet/location-summary`，增强 `/api/fleet/latest-locations` 查询能力。
- 小程序司机端支持持续位置上报：开启后每 30 秒同步一次。
- React Map 页面改为中文车队地图：车辆 marker、位置列表、在线状态、最新位置时间、搜索和筛选。
- Driver Monitor 继续展示司机最新位置，并修复位置查询类型问题。

## 关键文件
- `backend/services/location_service.py`
- `backend/api/routes.py`
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`
- `frontend/src/pages/MapPage.tsx`
- `frontend/src/pages/DriverMonitorPage.tsx`
- `frontend/src/services/apiClient.ts`

## 验证结果
- 后端编译通过。
- 司机 API 验证通过：位置日志写入、最新位置查询、司机隔离均通过。
- 小程序 JS 语法检查通过。
- React build 通过。
- React lint 通过。
- health check 通过。
- `http://127.0.0.1:5173/#map` 可访问。
- `/api/fleet/latest-locations?limit=5` 返回最新位置数据。

## 风险
- 当前地图为坐标示意图，不接第三方地图底图。
- 当前刷新为 5 秒 polling，不做 WebSocket。
- 持续定位依赖微信真机授权，需要人工验证。
