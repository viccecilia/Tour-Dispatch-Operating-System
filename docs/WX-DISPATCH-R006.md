# WX-DISPATCH-R006 司机端执行闭环

本轮新增轻量司机端执行闭环：

- 司机按 `driver_id` 查看自己的 active assignments
- 司机查看订单详情
- 司机提交执行报备
- 报备写入 `driver_reports`
- 报备同步更新 `assignments.execution_status` 和 `orders.execution_status`
- 调度端 assignment 列表展示 execution_status 和最新报备
- dashboard 展示今日执行状态统计
- 小程序新增司机端页面

司机身份识别：

- 本轮不接微信正式登录。
- API 使用 query 参数 `driver_id` 或 header `X-Driver-Id` 识别司机。

执行状态：

- `assigned`
- `confirmed`
- `departed`
- `arrived`
- `in_service`
- `completed`
- `returned`

本轮不包含实时地图、轨迹回放、WebSocket、第三方地图、复杂定位、真实照片上传、照片审核流。
