# TASK-003 Dispatch Quick Assign Polish

- 派车页新增顶部压力条：
  - 未派车
  - 已选择
  - 可见司机
  - 一键接龙
- 保留现有包车、接机、送机、司机、车辆四块结构和底部派车条。
- 涉及文件：
  - `miniapp_dispatch/pages/dispatch/index.wxml`
  - `miniapp_dispatch/pages/dispatch/index.wxss`
- 验证方式：
  - `node --check miniapp_dispatch/pages/dispatch/index.js`
- 状态：DONE
- 风险：真正高并发 50-80 单时仍需真机滑动体验验证。
