# WX-DISPATCH-R005 订单解析增强

本轮新增高效率订单录入草稿链路：

- 粘贴中文订单文本生成草稿
- CSV / rows 形式 Excel 入口生成草稿
- 语音转文字入口生成 voice 草稿
- 原始文本保留
- 草稿可人工修正
- 草稿确认后才写入正式 `orders`
- 失败或作废草稿不丢原文

后端 API：

- `POST /api/parser/text`
- `POST /api/parser/excel`
- `POST /api/parser/voice`
- `GET /api/parser/drafts`
- `GET /api/parser/drafts/{id}`
- `PUT /api/parser/drafts/{id}`
- `DELETE /api/parser/drafts/{id}`：作废草稿，不物理删除文本
- `POST /api/parser/drafts/{id}/confirm`

本轮不接 OpenAI API，不做复杂 NLP，不做聊天机器人 UI。
