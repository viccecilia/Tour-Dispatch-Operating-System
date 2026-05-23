# TASK-004：Excel 导出

## 修改了什么
- 新增 `GET /api/finance/export`。
- 返回 UTF-8 BOM CSV，可用 Excel 打开。
- 前端新增“导出 Excel/CSV”按钮。

## 涉及文件
- `backend/services/finance_service.py`
- `backend/api/routes.py`
- `frontend/src/services/apiClient.ts`
- `frontend/src/pages/FinancePage.tsx`

## 验证方式
- `python scripts/verify_finance_api.py`

## 是否完成
DONE

## 风险
- 当前导出 CSV，不是原生 `.xlsx`。Excel 可以直接打开，但后续可升级为 xlsx。
