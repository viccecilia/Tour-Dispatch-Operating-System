# WX-DISPATCH-R004 派车日历视图

本轮新增派车日历可视化：

- 从 `orders + assignments + drivers + vehicles` 读取 active 派车记录
- 支持 `day` / `week` / `month` 三种 API 视图
- 小程序端支持 24h / 7日 / 本月视图
- 车辆纵向、时间横向展示当天派车
- 颜色图例区分订单类型和状态
- 点击订单查看详情
- dashboard 接入今日派车摘要

后端 API：

- `GET /api/calendar/dispatch`
- `GET /api/calendar/dispatch/detail/{assignment_id}`

本轮不包含拖拽日历、地图路径规划、司机端闭环、定位、照片、财务结算计算和微信正式登录授权。
