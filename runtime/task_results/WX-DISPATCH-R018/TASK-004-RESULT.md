# TASK-004：调度端位置监控

## 修改了什么
- Driver Monitor 增加“在线车辆”KPI。
- 任务卡片展示最新位置。
- 右侧增加“车队位置监控”坐标列表。
- 当前为地图占位能力：先显示坐标和位置文字，不强依赖第三方地图。

## 涉及文件
- `frontend/src/pages/DriverMonitorPage.tsx`
- `frontend/src/services/apiClient.ts`
- `frontend/src/types/api.ts`

## 验证方式
- `npm.cmd run build`
- `npm.cmd run lint`
- 浏览器检查 `#driver-monitor`：
  - “车队位置监控”可见
  - “在线车辆”可见
  - 坐标和测试位置文字可见

## 是否完成
DONE

## 风险
- 未做真实地图渲染，只做第一版坐标列表。
