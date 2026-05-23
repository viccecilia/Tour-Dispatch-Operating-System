# TASK-003 财务同步

## 修改了什么
- 财务验证脚本增加司机收入 API 校验。
- 财务端更新司机垫付、代收、司机结算金额后，司机收入 API 能同步看到待结算金额。
- 继续验证财务修改写入 audit logs。

## 涉及文件
- `scripts/verify_finance_ledger.py`
- `backend/services/finance_service.py`

## 验证方式
- `python scripts/verify_finance_ledger.py`

## 是否完成
DONE

## 风险
- 当前同步是查询实时聚合，不是单独生成工资单快照；正式结算单需要后续冻结数据。
