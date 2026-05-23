# TASK-005 前端与主链路回归

## 修改了什么
- 前端 Finance 继续使用已有司机结算统计区。
- 本轮没有改变财务台账主表和订单、派车、司机状态主链路。

## 涉及文件
- `frontend/src/pages/FinancePage.tsx`
- `frontend/src/services/apiClient.ts`

## 验证方式
- `cd frontend && npm.cmd run build`
- `cd frontend && npm.cmd run lint`
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 财务端仍缺正式“工资单/结算单”冻结动作。
