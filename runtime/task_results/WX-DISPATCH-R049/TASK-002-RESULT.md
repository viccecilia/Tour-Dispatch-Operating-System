# TASK-002：财务确认 / 驳回

## 修改了什么
- 新增财务端司机费用更新能力：`PUT /api/finance/driver-expenses/{id}`
- 支持将费用状态改为 `confirmed` 或 `rejected`。
- 财务确认后同步回写订单上的司机垫付 / 代收汇总金额。

## 涉及文件
- `backend/services/finance_service.py`
- `backend/api/routes.py`

## 验证方式
- `python scripts/verify_finance_ledger.py`

## 是否完成
- DONE

## 风险
- 目前驳回只改变状态和备注，不做复杂申诉或二次审核流。
