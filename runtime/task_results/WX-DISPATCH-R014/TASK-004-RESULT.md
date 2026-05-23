# TASK-004：前端资源管理页

## 修改了什么
- 重做 Vehicles 页面为资源管理模块。
- 顶部显示提醒中心。
- 支持车辆台账与司机台账切换。
- 左侧新增/编辑表单，右侧台账表格。

## 涉及文件
- `frontend/src/pages/VehiclesPage.tsx`

## 验证方式
- `npm.cmd run build`
- `npm.cmd run lint`
- 浏览器打开 `http://127.0.0.1:18765/?v=r014#vehicles`，确认提醒中心、车辆台账、司机台账可见。

## 是否完成
DONE

## 风险
- UI 是最小可用版，后续可以增加批量导入和证件照片。
