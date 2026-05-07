# TASK-005 结果

状态：DONE

修改了什么：

- dashboard summary 增加：
  - 待确认草稿数
  - 今日解析订单数
  - 解析失败数
- 后端 dashboard HTML 首页展示解析统计。
- 小程序首页展示今日订单、未分配订单、已派车订单、待确认草稿、解析失败、今日解析。

涉及文件：

- `backend/services/dashboard_service.py`
- `backend/api/routes.py`
- `miniapp/pages/index/index.js`
- `miniapp/pages/index/index.wxml`

验证方式：

- `python scripts/verify_parser_api.py`
- `GET /api/dashboard/summary`

是否完成：是

风险：

- 今日解析按草稿 `created_at` 日期统计，不代表最终订单服务日期。
