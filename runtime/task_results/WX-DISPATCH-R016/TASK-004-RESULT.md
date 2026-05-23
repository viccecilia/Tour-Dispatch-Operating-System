# TASK-004：同车多单建议

## 修改了什么
- route summary 增加 `same_vehicle_suggestion`。
- 当多订单接龙无风险且平均分较高时，提示可考虑同车多单。

## 涉及文件
- `backend/services/dispatch_service.py`
- `frontend/src/pages/DispatchPage.tsx`

## 验证方式
- `npm.cmd run build`
- `GET /api/dispatch/route-suggestion`

## 是否完成
DONE

## 风险
- 当前建议没有考虑司机工时、休息、车辆返场等更复杂约束。
