# TASK-004 车辆 marker 与最新位置时间

## 修改了什么
- 地图页 marker 显示车牌、司机和在线颜色。
- 右侧位置列表显示车牌、司机、文字位置、经纬度、最新上报时间和当前任务。
- 在线为绿色，未刷新为橙色。

## 涉及文件
- `frontend/src/pages/MapPage.tsx`
- `backend/services/location_service.py`

## 验证方式
- `/api/fleet/latest-locations?limit=5` 返回司机、车牌、坐标、时间、在线状态。
- `cd frontend && npm.cmd run build`

## 是否完成
DONE

## 风险
- 坐标投影是演示用简化算法，不代表真实地图距离。
