# TASK-005：财务验证脚本

## 修改了什么
- 新增 `scripts/verify_finance_api.py`。
- 覆盖订单创建、待结算统计、结算状态修改、导出内容验证。

## 涉及文件
- `scripts/verify_finance_api.py`

## 验证方式
- `python scripts/verify_finance_api.py`

## 是否完成
DONE

## 风险
- 验证脚本会新增测试订单，演示前建议重置 demo 数据。
