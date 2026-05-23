# TASK-005 结果：Live Fleet Runtime

## 修改了什么
- 地图页升级为运行核心页面：
  - 顶部 Runtime 指标
  - 搜索和状态筛选
  - 大地图区域
  - 订单覆盖层
  - 风险司机列表
  - 附近可派司机
- 页面自动 5 秒刷新位置，8 秒刷新安全告警。

## 涉及文件
- `frontend/src/pages/MapPage.tsx`
- `scripts/verify_live_map_runtime.py`

## 验证方式
- `python -m compileall backend scripts`
- `python scripts/reset_demo_db.py`
- `python scripts/health_check.py`
- `python scripts/verify_live_map_runtime.py`
- `python scripts/verify_dispatch_api.py`
- `python scripts/verify_driver_api.py`
- `cd frontend && npm.cmd run build`
- `cd frontend && npm.cmd run lint`

## 是否完成
DONE

## 风险
- 真实底图未接入，本轮没有做轨迹回放、热力图、路线规划。
