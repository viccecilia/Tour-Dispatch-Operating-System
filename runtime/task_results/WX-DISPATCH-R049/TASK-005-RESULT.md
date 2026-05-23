# TASK-005：财务 Dashboard 更新与审计

## 修改了什么
- 财务 ledger summary 增加司机费用待确认统计。
- 财务确认 / 驳回司机费用写入 `audit_logs`。
- 验证脚本补充司机费用提交流程、财务确认 / 驳回、审计检查。

## 涉及文件
- `backend/services/finance_service.py`
- `backend/api/routes.py`
- `scripts/verify_finance_ledger.py`

## 验证方式
- `python scripts/verify_finance_ledger.py`

## 是否完成
- DONE

## 风险
- Dashboard 主首页只通过财务 summary 暴露数据，是否需要放入运营首页 KPI 仍需人工决定。
