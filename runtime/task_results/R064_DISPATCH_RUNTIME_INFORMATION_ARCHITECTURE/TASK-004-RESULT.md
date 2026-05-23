# TASK-004 Mobile Dispatch Pressure Feeling

- 首页用红黄风险卡表达未派车、待确认和高风险。
- 地图页增加在线司机、即将开始、风险订单摘要。
- 财务页改为今日财务待办，突出今日垫付、异常费用、待确认。
- 涉及文件：
  - `miniapp_dispatch/pages/index/index.wxml`
  - `miniapp_dispatch/pages/map/index.wxml`
  - `miniapp_dispatch/pages/finance/index.wxml`
  - 对应 wxss 文件
- 验证方式：
  - `node --check miniapp_dispatch/pages/map/index.js`
  - `node --check miniapp_dispatch/pages/finance/index.js`
- 状态：DONE
- 风险：风险状态目前主要是显示层聚合，后续可接入严格的迟到/未确认/冲突计算。
