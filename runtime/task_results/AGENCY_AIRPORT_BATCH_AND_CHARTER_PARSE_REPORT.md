# 旅行社机场批量解析与包车单条解析测试报告

## 范围

- 机场接送支持批量文本解析。
- 批量解析后生成多条旅行社订单预览，可批量导入。
- 包车支持单条大段文本解析。
- 包车解析后自动填入表单字段，包括酒店、行程备注、车型、人数、导游联系方式、报价等。

## 修改文件

- `backend/services/agency_portal_service.py`
- `backend/api/routes.py`
- `frontend/src/services/apiClient.ts`
- `frontend/src/pages/AgencyPortalPage.tsx`

## 新增接口

- `POST /api/agency-portal/orders/parse`
  - `mode=airport_batch`：机场接送批量解析。
  - `mode=charter`：包车单条解析。
  - 只解析，不生成调度草稿，不写入订单；旅行社确认导入后才创建订单。

## 本地验证

- `python -m py_compile backend\services\agency_portal_service.py backend\api\routes.py`
  - 结果：通过。
- `npm.cmd run build`
  - 结果：通过。
  - 备注：Vite 仍提示单个 chunk 超过 500 kB，为既有体积警告。

## 隔离数据库验证

测试库：

- `runtime/test_dbs/agency_parse_modes.sqlite3`

验证步骤：

1. 创建旅行社并登录门户。
2. 输入两条机场接送文本。
3. 调用旅行社解析接口，解析为 2 条订单。
4. 输入一条包车大段文本。
5. 调用旅行社解析接口，解析为 1 条订单。
6. 用解析出的包车字段创建旅行社订单。

验证结果：

- 机场接送批量文本解析为 2 单。
- 机场接送解析结果 `order_type=airport_transfer`。
- 包车解析结果 `order_type=charter`。
- 包车解析出酒店作为起终点。
- 包车解析出车型、人数、导游姓名、导游微信、报价。
- 解析出的包车字段可成功创建订单。

## 浏览器验证

- `http://127.0.0.1:5173/#agency-portal`
- 已显示：
  - `包车文本解析`
  - `解析包车并填表`
  - `机场接送批量入单`
  - `解析机场接送`

## 未执行事项

- 未进行云端部署。
- 未修改生产数据库。
- 未 Git push。
- 未上传小程序。
