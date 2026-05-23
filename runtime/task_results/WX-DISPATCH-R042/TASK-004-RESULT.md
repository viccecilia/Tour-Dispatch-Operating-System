# TASK-004 司机数据与销售价格隔离

## 修改了什么
- 页面继续使用现有司机 API：任务、工作台、提醒、费用、履历、照片、位置。
- 司机端订单展示保留时间、路线、客人、电话、状态，不显示订单销售价格。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`

## 验证方式
- `python scripts/verify_driver_api.py`
- 代码扫描：司机 WXML 未出现 `price`、`订单价格`、`售价`。

## 是否完成
DONE

## 风险
- 司机费用页会显示司机提交的垫付/代收金额，这不是订单销售价格。
