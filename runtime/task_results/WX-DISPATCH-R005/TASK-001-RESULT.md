# TASK-001 结果

状态：DONE

修改了什么：

- 新增 `order_drafts` 表。
- 字段覆盖 raw_text、source_type、parse_status、订单草稿字段、parse_result_json、confirmed_order_id、created_at、updated_at。
- 初始化流程加入兼容迁移。
- 原始文本 `raw_text` 为必保留字段。

涉及文件：

- `backend/db/schema.sql`
- `backend/db/database.py`
- `scripts/init_db.py`

验证方式：

- `python scripts/init_db.py`
- `python scripts/verify_parser_api.py`

是否完成：是

风险：

- 草稿状态为轻量状态机，未引入复杂审核流。
