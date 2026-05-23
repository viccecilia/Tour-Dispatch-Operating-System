# TASK-001：司机费用进入财务待确认池

## 修改了什么
- 新增财务端司机费用读取能力：`GET /api/finance/driver-expenses`
- 将司机端提交的 `driver_expense_reports` 按 `submitted / in_hand` 识别为财务待确认费用。
- 财务 summary / ledger 增加司机费用待确认统计。

## 涉及文件
- `backend/services/finance_service.py`
- `backend/api/routes.py`
- `frontend/src/services/apiClient.ts`
- `frontend/src/types/api.ts`

## 验证方式
- `python scripts/verify_finance_ledger.py`

## 是否完成
- DONE

## 风险
- 当前待确认池基于现有 `driver_expense_reports`，没有引入独立会计凭证表。
