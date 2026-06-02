# 旅行社/车公司航班信息 MVP 验证报告

## 执行范围

- 新增订单航班字段：航班号、航班日期、航空公司、起降地、航站楼、登机口、状态、计划/预计/实际起降时间、数据来源、最后查询时间、人工备注。
- 新增后端航班查询服务：未配置真实 API key 时返回本地模拟数据；保留手动录入字段。
- 新增旅行社端接口：
  - `POST /api/agency-portal/flight-info/query`
  - `POST /api/agency-portal/orders/{id}/flight-info`
- 新增后台车公司/管理端接口：
  - `POST /api/flight-info/query`
  - `POST /api/orders/{id}/flight-info`
- 旅行社 Web 单条入单增加“航班信息 MVP”和“查询航班”按钮。
- 旅行社 Web 订单跟踪表增加航班查询/保存单元。
- 车公司订单大厅和结算联动区增加航班摘要展示。

## 本地模拟数据链

测试数据：

- 旅行社：MVP旅行社
- 订单：2026-06-10 09:30 关西机场T1 -> Osaka Namba Hotel
- 航班号：JL225

验证结果：

- `query_agency_flight_info` 返回 `mode=mock`。
- `update_agency_order_flight_info` 写入订单航班状态：`前方候机`。
- `list_agency_orders` 可读取 `flight_number=JL225`。
- 发布到订单大厅后，`list_auction_listings("listed")` 可读取 `flight_number=JL225`。

## 验证命令

- `python -m py_compile backend\services\flight_info_service.py backend\services\agency_portal_service.py backend\services\auction_service.py backend\services\order_service.py backend\api\routes.py`
- `npm.cmd run build`
- 临时 SQLite 数据链脚本：`runtime/test_dbs/flight_mvp.sqlite3`
- 本地后端实时接口：
  - `POST http://127.0.0.1:18765/api/flight-info/query`
- 浏览器检查：
  - `http://127.0.0.1:5173/#agency-portal`
  - `http://127.0.0.1:5173/#auction`

## 验证结果

- Python 编译通过。
- 前端 TypeScript/Vite 构建通过，仅保留既有 Vite 大 chunk 警告。
- 本地后端已重启并通过 `GET /api/ping`。
- 实时航班查询接口返回 `mode=mock`、`flight_number=JL225`、`flight_status=前方候机`。
- 旅行社 Web 可见“航班信息 MVP”“查询航班”和本地模拟提示。
- 车公司订单大厅页面可正常打开；当前演示库无航班号的结算行显示占位，有航班号的数据链已通过临时库验证。

## 启动兼容修复

- 本地演示库存在历史 `orders.oid` 唯一约束冲突，导致后端重启时在 `refresh_order_oids` 抛出 `UNIQUE constraint failed: orders.oid`。
- 已做最小兼容：刷新订单号时如果候选编号已存在，则顺延当日流水号。
- 未删除、未清理、未重建真实数据。

## 官网公开信息策略

- MVP 不做网页抓取，不把官网页面 HTML 当稳定接口。
- 可以在返回结果里提供航空公司/机场官网查询入口，供人工核验。
- 推荐正式上线时使用 FlightAware AeroAPI、Cirium 等有授权和 SLA 的 API；供应商和 API key 确认前继续走本地模拟/手动录入。
