# TASK-001：订单价格管理

## 修改了什么
- 财务汇总读取订单价格、费用备注、结算状态。
- 财务订单列表支持按旅行社、日期、结算状态筛选。
- 结算状态更新接口可同时保留价格字段基础能力。

## 涉及文件
- `backend/services/finance_service.py`
- `backend/api/routes.py`
- `frontend/src/pages/FinancePage.tsx`

## 验证方式
- `python scripts/verify_finance_api.py`

## 是否完成
DONE

## 风险
- 本轮不做复杂费用拆分和会计科目。
