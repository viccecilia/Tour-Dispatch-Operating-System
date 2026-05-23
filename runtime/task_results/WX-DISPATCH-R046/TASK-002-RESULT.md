# TASK-002 顶部 Driver Hero 重构

## 修改了什么
- 顶部状态卡增强为 Driver Hero。
- 显示司机姓名、在线状态、当前车辆、日期时间、司机 ID、当前状态。
- 状态颜色继续区分休息/未出库/已出库/已入库。

## 涉及文件
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`

## 验证方式
- `node --check miniapp/pages/driver/index.js`

## 是否完成
DONE

## 风险
- 车辆显示依赖当前 assignment 的车辆字段，缺失时显示未绑定车辆。
