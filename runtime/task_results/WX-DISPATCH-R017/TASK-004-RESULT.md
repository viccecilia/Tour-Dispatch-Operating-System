# TASK-004：Driver Monitor 调度端升级

## 修改了什么
- React Driver Monitor 页面升级为 KPI + 执行任务 + 最新报备。
- 增加执行中、服务中、已完成/归库、未报备 KPI。
- 每个任务展示状态时间线：待确认 -> 已确认 -> 已出库 -> 已到达 -> 服务中 -> 已完成 -> 已归库。

## 涉及文件
- `frontend/src/pages/DriverMonitorPage.tsx`

## 验证方式
- `npm.cmd run build`
- `npm.cmd run lint`
- 浏览器检查 `#driver-monitor`，确认“司机执行监控 / 最新司机报备 / 状态时间线”可见。

## 是否完成
DONE

## 风险
- 本轮不做 WebSocket，继续使用轮询刷新。
