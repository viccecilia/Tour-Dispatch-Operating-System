# TASK-002 Driver Timeline Runtime

- 新增 `todayTimeline` 数据结构，用今日订单生成“点呼出库 -> 订单开始/送达 -> 归库收工”的轻量时间轴。
- 时间轴按订单开始时间排序，跨业务状态不改变后端，只作为司机端视觉组织。
- 涉及文件：
  - `miniapp/pages/driver/index.js`
  - `miniapp/pages/driver/index.wxml`
  - `miniapp/pages/driver/index.wxss`
- 验证方式：
  - `node --check miniapp/pages/driver/index.js`
  - `python scripts/verify_driver_api.py`
- 状态：DONE
- 风险：出库时间当前按第一单前 60 分钟推算，后续可接入真实公司点呼规则。
