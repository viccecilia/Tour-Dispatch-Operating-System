# R066 总结：LIVE MAP RUNTIME

## 修改了什么
- 重构 Web 地图页为 Live Fleet Runtime。
- 增加司机实时 marker、订单覆盖层、附近可派司机、风险高亮和运行态指标。
- 新增 `scripts/verify_live_map_runtime.py`，验证位置上报到地图页数据链路。

## 涉及文件
- `frontend/src/pages/MapPage.tsx`
- `scripts/verify_live_map_runtime.py`

## 每个任务状态
- TASK-001: DONE
- TASK-002: DONE
- TASK-003: DONE
- TASK-004: DONE
- TASK-005: DONE

## 验证结果
- `python -m compileall backend scripts`：通过。
- `python scripts/reset_demo_db.py`：通过，重置 demo 数据。
- `python scripts/health_check.py`：通过。
- `python scripts/verify_live_map_runtime.py`：通过，位置写入、latest location、assignment overlay、online filter、summary、safety alerts 均可用。
- `python scripts/verify_dispatch_api.py`：通过。
- `python scripts/verify_driver_api.py`：通过。首次普通 PowerShell 输出遇到 cp932 中文编码问题，设置 `PYTHONIOENCODING=utf-8` 后通过。
- `cd frontend && npm.cmd run build`：通过。
- `cd frontend && npm.cmd run lint`：通过。

## 协作验收结果
- 需要人工打开 Web Console 的地图页确认视觉和交互：
  - marker 是否容易理解
  - 订单覆盖层是否够清楚
  - 风险红色高亮是否显眼但不吵
  - 附近可派司机是否对调度有帮助

## 未完成/风险
- 当前地图是轻量运行视图，不是 Google Maps / 腾讯地图真实底图。
- 当前“附近司机”还不是基于真实半径距离计算。
- 当前没有轨迹回放、偏航检测、热力图、路线规划。

## 下一轮建议
- R067 可做 `REAL_MAP_PROVIDER_INTEGRATION`：接入真实地图底图，并保留当前 marker、订单覆盖层、风险高亮和司机筛选逻辑。
