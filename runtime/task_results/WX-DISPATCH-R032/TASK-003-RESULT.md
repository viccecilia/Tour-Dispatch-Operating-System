# TASK-003 调度地图页

## 修改了什么
- 重做 React Map 页面为中文车队实时地图。
- 提供车辆 marker 示意面板、最新位置列表、在线/未刷新统计。
- 支持搜索司机、车牌、位置、订单号。
- 支持在线状态筛选。
- 每 5 秒自动刷新。

## 涉及文件
- `frontend/src/pages/MapPage.tsx`
- `frontend/src/services/apiClient.ts`

## 验证方式
- `cd frontend && npm.cmd run build`
- `cd frontend && npm.cmd run lint`
- `http://127.0.0.1:5173/#map` 返回 200

## 是否完成
DONE

## 风险
- 当前是不接第三方底图的坐标示意图，不做路径规划和轨迹。
