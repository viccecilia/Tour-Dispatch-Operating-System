# TASK-003 当前车辆状态 / 当前订单状态 / driver marker

## 修改了什么
- Fleet Map marker 根据车辆状态和在线状态使用不同颜色。
- 最新位置卡片显示：
  - 司机
  - 车辆
  - 车辆状态
  - 当前订单状态
  - 派车状态
  - 最新坐标
  - 上报时间
  - 当前订单路线

## 涉及文件
- `frontend/src/pages/MapPage.tsx`
- `frontend/src/types/api.ts`

## 验证方式
- 浏览器检查 `#map` 页面包含车辆状态、订单状态和最新位置列表。
- `npm.cmd run build`
- `npm.cmd run lint`

## 是否完成
DONE

## 风险
- marker 坐标投影是轻量近似映射，用于演示和运营定位概览，不是正式 GIS 坐标底图。
