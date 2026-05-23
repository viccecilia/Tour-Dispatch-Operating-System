# WX-DISPATCH-R033 Driver Income & Settlement

## 本轮完成内容
- 新增司机收入 API：`GET /api/driver/income`。
- 司机端显示今日收入、本月收入、垫付、代收、待结算、已结算和完成单。
- 财务验证脚本确认财务端维护金额后，司机收入 API 能同步反映。
- 继续保证司机端不暴露订单销售价格。

## 关键文件
- `backend/services/finance_service.py`
- `backend/api/routes.py`
- `miniapp/utils/api.js`
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`
- `scripts/verify_finance_ledger.py`

## 验证结果
- 后端编译通过。
- health check 通过。
- 财务专项验证通过。
- 司机 API 回归通过。
- 小程序 JS 语法检查通过。
- React build 通过。
- React lint 通过。

## 风险
- 当前是收入汇总，不是正式工资单。
- demo 数据司机工资字段不足时，司机端收入可能显示 0。
- 不接真实支付、不做复杂工资系统。
