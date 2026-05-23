# WX-DISPATCH-R015：Finance & Settlement System

## 本轮结果
- 建立财务结算页，替换原 Finance 占位页。
- 支持订单价格与费用备注展示。
- 支持旅行社待结算、已结算金额统计。
- 支持司机结算基础统计。
- 支持车辆收入统计。
- 支持修改订单结算状态。
- 支持导出基础财务 CSV，可用 Excel 打开。

## 验证结果
- `python -m compileall backend scripts`：通过。
- `python scripts/verify_finance_api.py`：通过。
- `npm.cmd run build`：通过。
- `npm.cmd run lint`：通过。
- 浏览器检查 `#finance`：财务结算页、导出按钮、旅行社待结算均可见。

## 风险
- 不接支付、不做发票、不做复杂会计科目。
- 导出格式是 CSV，不是原生 xlsx。
- 司机工资、车辆成本和利润核算暂未实现。

## 下一轮建议
- 增加结算批次、对账单、导出 xlsx 模板。
- 增加司机工资规则和车辆成本字段。
