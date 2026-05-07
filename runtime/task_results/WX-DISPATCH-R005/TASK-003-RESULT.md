# TASK-003 结果

状态：DONE

修改了什么：

- 新增 parser API：
  - `POST /api/parser/text`
  - `POST /api/parser/excel`
  - `POST /api/parser/voice`
  - `GET /api/parser/drafts`
  - `GET /api/parser/drafts/{id}`
  - `PUT /api/parser/drafts/{id}`
  - `DELETE /api/parser/drafts/{id}`
  - `POST /api/parser/drafts/{id}/confirm`
- 草稿确认后写入 `orders`。
- 确认后更新 `parse_status = confirmed` 和 `confirmed_order_id`。
- Excel 入口支持 CSV 文本和 rows 数据；voice 入口支持 voice_text/mock 文本。

涉及文件：

- `backend/api/routes.py`
- `backend/services/parser_service.py`

验证方式：

- `python scripts/verify_parser_api.py`

是否完成：是

风险：

- xlsx 不做二进制文件解析；本轮仅提供轻量 rows / csv 入口。
