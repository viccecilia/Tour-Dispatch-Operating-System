# TASK-002 结果

状态：DONE

修改了什么：

- 新增 `backend/services/parser_service.py`。
- 使用正则和关键词解析中文订单。
- 尝试解析日期、时间、路线、人数、行李数、车型、客人、电话、旅行社、价格、备注。
- 解析失败仍生成 failed 草稿，并保留 raw_text。
- parse_result_json 保存解析结果。

涉及文件：

- `backend/services/parser_service.py`

验证方式：

- `python -m compileall backend`
- `python scripts/verify_parser_api.py`

是否完成：是

风险：

- 解析器是规则型轻量实现，不保证复杂自然语言准确率。
