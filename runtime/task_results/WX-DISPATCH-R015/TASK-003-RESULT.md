# TASK-003：司机结算基础与车辆收入统计

## 修改了什么
- 财务 summary 增加司机维度统计。
- 财务 summary 增加车辆维度统计。
- 前端显示司机结算基础和车辆收入统计卡片。

## 涉及文件
- `backend/services/finance_service.py`
- `frontend/src/pages/FinancePage.tsx`

## 验证方式
- `python scripts/verify_finance_api.py`
- `npm.cmd run build`

## 是否完成
DONE

## 风险
- 司机工资、车辆成本、利润核算不在本轮范围。
