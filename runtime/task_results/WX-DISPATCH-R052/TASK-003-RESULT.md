# TASK-003 Driver Monitor evidence viewer

## 修改了什么
- Driver Monitor 任务卡增加“查看执行证据”按钮。
- 右侧新增订单执行证据面板，显示：
  - 照片数
  - 报备数
  - 小票/费用数
  - 下载数
  - timeline 明细
  - 打开/下载证据链接

## 涉及文件
- `frontend/src/pages/DriverMonitorPage.tsx`
- `frontend/src/services/apiClient.ts`

## 验证方式
- `npm.cmd run build`
- `npm.cmd run lint`
- 浏览器打开 `http://127.0.0.1:5173/#driver-monitor` 确认“订单执行证据”和“查看执行证据”可见。

## 是否完成
DONE

## 风险
- 当前为查看型面板，没有做审核状态流。
