# TASK-001 司机收入汇总

## 修改了什么
- 新增司机收入汇总 API：`GET /api/driver/income`。
- 返回今日收入、本月收入、完成单数、垫付、代收、待结算、已结算。
- 司机端只展示司机工资和结算信息，不返回订单销售价格。

## 涉及文件
- `backend/services/finance_service.py`
- `backend/api/routes.py`
- `miniapp/utils/api.js`
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`

## 验证方式
- `python scripts/verify_finance_ledger.py`

## 是否完成
DONE

## 风险
- demo 数据里司机工资字段不一定完整，真实收入展示依赖后续录入司机工资/结算金额。
