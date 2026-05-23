# TASK-001 Fleet Map 页面

## 修改了什么
- 将 React 地图页升级为“车队地图监控”页面。
- 页面显示车队总数、在线、已出库、服务中、未刷新 KPI。
- 地图 marker 显示司机、车辆、当前订单执行状态。
- 右侧最新位置列表显示车辆状态、订单状态、坐标、上报时间和当前路线。

## 涉及文件
- `frontend/src/pages/MapPage.tsx`
- `frontend/src/types/api.ts`
- `frontend/src/services/apiClient.ts`

## 验证方式
- `npm.cmd run build`
- `npm.cmd run lint`
- 浏览器打开 `http://127.0.0.1:5173/#map` 检查页面关键文案和状态区。

## 是否完成
DONE

## 风险
- 当前 Web 调度端仍为轻量地图画布，不接入第三方地图底图，不做轨迹回放。
