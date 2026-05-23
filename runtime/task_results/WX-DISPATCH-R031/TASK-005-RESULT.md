# TASK-005 司机体验、失败提示与收入

## 修改了什么
- 弱网/离线时报备暂存本地，恢复网络后可重试。
- 页面显示网络状态、最后同步时间、待重试数量。
- 今日收入显示使用司机工资字段聚合，不暴露订单销售价格。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `backend/services/driver_service.py`

## 验证方式
- `python scripts/verify_driver_api.py`
- `node --check miniapp/pages/driver/index.js`

## 是否完成
DONE

## 风险
- demo 数据多数没有司机工资字段，所以验证输出中预计收入可能为 0；真实数据录入司机工资后会显示。
