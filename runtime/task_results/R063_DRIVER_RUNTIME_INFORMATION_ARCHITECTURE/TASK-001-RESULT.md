# TASK-001 Driver Home Simplification

- 修改了司机端首页结构：首页保留待确认接单、当前任务、出入库/清扫/酒测状态、今日时间轴。
- 移除了首页上的完整出库/入库 checklist 和月度 KPI 堆叠，避免打开后像后台表单。
- 涉及文件：
  - `miniapp/pages/driver/index.wxml`
  - `miniapp/pages/driver/index.wxss`
  - `miniapp/pages/driver/index.js`
- 验证方式：
  - `node --check miniapp/pages/driver/index.js`
  - `python scripts/verify_driver_api.py`
- 状态：DONE
- 风险：需要在微信开发者工具真机/模拟器里人工确认首页视觉是否足够清爽。
