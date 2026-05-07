# wx_dispatch_platform

本仓库当前采用根级 `backend/`、`miniapp/`、`docs/`、`scripts/`、`runtime/` 目录承载最小可运行框架。

保留该目录作为项目命名入口，避免复制两套后端和小程序代码。

## 当前能力

- R001：基础 API、SQLite 初始化、admin 登录、运营中台首页骨架。
- R002：订单新增、订单列表筛选、订单编辑、订单软删除、dashboard 订单统计。
- R003：未分配订单派车、司机车辆选择、assignments 历史、取消/重新分配、时间冲突检测、接龙建议。
- R004：派车日历 API、小程序 24h/7日/本月视图、订单详情区、今日派车 dashboard 摘要。
- R005：文本/Excel/语音入口生成订单草稿、人工修正、确认入库、解析统计。
- R006：司机端我的订单、执行报备、driver_reports、execution_status 回写、调度端和 dashboard 执行状态可见。
