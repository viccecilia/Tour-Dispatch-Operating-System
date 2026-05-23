# WX-DISPATCH-R049：Expense ↔ Finance Runtime

## 本轮完成内容
- 司机提交的垫付 / 代收费用可以进入财务待确认池。
- 财务端可以确认或驳回司机费用。
- 财务确认后同步影响订单财务字段和司机结算统计。
- 财务页面新增司机费用待确认区。
- 财务费用修改写入审计日志。
- 验证脚本覆盖费用提交、财务确认、财务驳回、dashboard/ledger 变化、司机端价格隐藏。

## 验证结果
- `python -m compileall backend scripts`：通过
- `python scripts/reset_demo_db.py`：通过
- `python scripts/health_check.py`：通过
- `python scripts/verify_finance_ledger.py`：通过
- `npm.cmd run build`：通过
- `npm.cmd run lint`：通过

## 协作验收
- 需要人工确认司机费用待确认池的字段顺序是否符合财务习惯。
- 需要人工确认“确认 / 驳回”是否够直观。

## 风险
- 未接真实支付。
- 未做复杂会计科目、发票、付款审批。
- 司机端仍是提交入口，财务审核在 React Finance 页面完成。
