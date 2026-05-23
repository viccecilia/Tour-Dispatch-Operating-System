# TASK-003：司机结算联动

## 修改了什么
- 财务确认司机费用后，订单财务字段会重新汇总：
  - `driver_advance_amount`
  - `driver_collect_amount`
  - `driver_settlement_amount`
- 司机收入接口继续隐藏订单销售价格。

## 涉及文件
- `backend/services/finance_service.py`
- `scripts/verify_finance_ledger.py`

## 验证方式
- `python scripts/verify_finance_ledger.py`

## 是否完成
- DONE

## 风险
- 司机结算金额当前仍按“垫付 - 代收”的轻量规则计算，未做复杂工资体系。
