# TASK-003：调度端显示确认状态

## 修改了什么
- React Dispatch 已分配订单池增加“司机确认”列。
- `execution_status = assigned` 显示为“未确认”。
- `confirmed / departed / arrived / in_service / completed / returned` 显示为“已确认”。
- 已分配订单池顶部增加“已派未确认”和“已确认司机”统计 chip。

## 涉及文件
- `frontend/src/pages/DispatchPage.tsx`

## 验证方式
- `npm run build`
- `npm run lint`
- 浏览器验证 `http://127.0.0.1:5173/#dispatch` 显示：
  - 已派未确认
  - 已确认司机
  - 司机确认

## 是否完成
DONE

## 风险
- 当前是轮询刷新，不是 WebSocket；状态变化会在现有刷新间隔后体现。
