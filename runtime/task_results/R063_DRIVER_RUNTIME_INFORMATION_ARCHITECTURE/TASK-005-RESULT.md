# TASK-005 Driver Calm UI Polish

- 调整司机端视觉密度：首页减少重色块和复杂表单，新增更轻的当前任务卡、状态条和时间轴。
- 任务页聚合今日订单、明日订单和历史订单。
- 费用页改为垫付、ETC、停车、夜班、代收五个轻入口。
- 我的页改为司机个人中心结构，只保留收入、证件、设置。
- 涉及文件：
  - `miniapp/pages/driver/index.wxml`
  - `miniapp/pages/driver/index.wxss`
- 验证方式：
  - `node --check miniapp/pages/driver/index.js`
- 状态：DONE
- 风险：UI 审美需要用户在模拟器中继续给截图反馈。
