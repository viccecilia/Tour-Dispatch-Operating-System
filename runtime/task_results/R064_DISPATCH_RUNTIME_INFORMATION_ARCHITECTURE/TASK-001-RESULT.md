# TASK-001 Dispatch Home Runtime Rebuild

- 将调度小程序首页从统计后台改成“调度待办中心”。
- 首页突出未派车、待确认、高风险、今日订单，并增加调度压力列表。
- 涉及文件：
  - `miniapp_dispatch/pages/index/index.wxml`
  - `miniapp_dispatch/pages/index/index.wxss`
- 验证方式：
  - `node --check miniapp_dispatch/pages/index/index.js`
  - `python scripts/verify_dispatch_mobile_runtime.py`
- 状态：DONE
- 风险：高风险数量依赖 dashboard API 当前字段，后续可细化迟到、未确认、异常费用等风险来源。
