# TASK-003 结果：Dispatch Radius

## 修改了什么
- 地图页底部增加“附近可派司机”区域。
- 优先展示在线、非服务中、非维修、非停用的司机。
- 用于调度临时派车时快速判断附近可用资源。

## 涉及文件
- `frontend/src/pages/MapPage.tsx`

## 验证方式
- `python scripts/verify_live_map_runtime.py`
- `npm.cmd run build`

## 是否完成
DONE

## 风险
- 当前没有真实距离计算和地图半径搜索，只按在线状态和车辆状态筛出可参考司机。
