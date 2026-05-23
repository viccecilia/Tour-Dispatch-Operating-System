# TASK-001：调度派车后司机端接收订单

## 修改了什么
- 保持派车写入 `assignments` 的既有链路。
- 司机端不再只保留今日订单，新增完整 assignment 缓存与明日订单拆分。
- 明日及未来已派未确认订单会显示在司机首页的“明日订单”区。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`

## 验证方式
- `python scripts/verify_dispatch_api.py`
- 验证项：`assign_tomorrow_success = true`
- 验证项：`tomorrow_order_visible_to_driver = true`

## 是否完成
DONE

## 风险
- 目前“明日订单”按 `order_date > today` 显示，跨时区日期仍沿用小程序当前日期逻辑。
