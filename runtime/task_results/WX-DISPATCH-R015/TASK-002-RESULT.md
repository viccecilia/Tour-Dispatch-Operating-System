# TASK-002：旅行社待结算与已结算状态

## 修改了什么
- 财务 summary 增加旅行社维度统计。
- 订单可从待结算改为已结算、已收款、未结账。
- 前端财务表中可直接修改结算状态。

## 涉及文件
- `backend/services/finance_service.py`
- `frontend/src/pages/FinancePage.tsx`

## 验证方式
- `python scripts/verify_finance_api.py`

## 是否完成
DONE

## 风险
- 当前没有结算批次号和对账单号，后续正式财务需要补。
