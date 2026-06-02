# 旅行社后台地图追踪与派单信息联动测试报告

## 范围

- 旅行社后台 Web 新增地图追踪模块。
- 旅行社订单列表只读展示车公司派单后的司机和车辆信息。
- 旅行社订单列表只读展示司机端最新位置上报信息。

## 修改文件

- `backend/services/agency_portal_service.py`
- `frontend/src/types/api.ts`
- `frontend/src/pages/AgencyPortalPage.tsx`

## 单元验证

- `python -m py_compile backend\services\agency_portal_service.py`
  - 结果：通过。
- `npm.cmd run build`
  - 结果：通过。
  - 备注：Vite 仍提示单个 chunk 超过 500 kB，这是既有打包体积警告，不影响本次功能。

## 数据链路验证

使用隔离测试库：

- `runtime/test_dbs/agency_map_tracking.sqlite3`

验证步骤：

1. 初始化隔离 SQLite 数据库。
2. 创建旅行社 `Map Test Agency` 并登录旅行社门户。
3. 旅行社录入一条订单。
4. 创建车公司司机和车辆。
5. 车公司执行派单，生成 active assignment。
6. 写入司机端位置上报。
7. 旅行社调用订单列表接口读取订单。

验证结果：

- 旅行社订单可读到 `dispatch_status=assigned`。
- 旅行社订单可读到 `assignment_id`。
- 旅行社订单可读到司机姓名、司机电话、司机编号、司机语言。
- 旅行社订单可读到车牌、车型、座位数、车辆颜色。
- 旅行社订单可读到司机最新位置文本、经纬度和上报时间。
- 查询按 `tenant_id + agency_id` 限定，未暴露其他旅行社或其他租户订单。

## 浏览器验证

目标页面：

- `http://127.0.0.1:5173/#agency-portal`

验证结果：

- 页面已渲染 `批量入单`。
- 页面已渲染 `订单跟踪`。
- 页面已渲染 `地图追踪`。

备注：

- 当前本地 18765 后端进程如未重启，不会自动加载本次 Python 后端修改；前端 Vite 页面可热更新。
- 派单后司机/车辆字段的接口联动已用隔离数据库脚本验证通过。
