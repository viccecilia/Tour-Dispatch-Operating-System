# TASK-001 结果：Driver Live Marker

## 修改了什么
- 重构 Web `MapPage`，从旧的坐标列表/占位地图升级为 Live Fleet Runtime 页面。
- 每个司机最新位置以 marker 展示，marker 显示司机、车辆、状态和当前位置。
- marker 颜色根据车辆状态和风险状态变化。

## 涉及文件
- `frontend/src/pages/MapPage.tsx`
- `scripts/verify_live_map_runtime.py`

## 验证方式
- `python scripts/verify_live_map_runtime.py`
- `python scripts/verify_driver_api.py`
- `npm.cmd run build`
- `npm.cmd run lint`

## 是否完成
DONE

## 风险
- 当前 Web 地图仍是轻量坐标运行视图，不是第三方真实底图；真实地图底图可在后续接入。
