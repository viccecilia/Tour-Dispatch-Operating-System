# TASK-002 垫付、代收、待结算、已结算

## 修改了什么
- 司机收入 API 汇总 `driver_advance_amount`、`driver_collect_amount`、`driver_settlement_amount`、`driver_settlement_status`。
- 小程序司机端增加“收入与结算”卡片。
- 显示本月收入、待结算、已结算、垫付、代收、完成单。

## 涉及文件
- `backend/services/finance_service.py`
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`

## 验证方式
- `python scripts/verify_finance_ledger.py`

## 是否完成
DONE

## 风险
- 本轮不支持司机自行申报垫付/代收，仍由财务端维护。
