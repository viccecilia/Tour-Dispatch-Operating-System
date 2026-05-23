# TASK-003 Driver UX 修复

## 修改了什么
- Driver Monitor 页面顶部增加试运营观察点：
  - 确认司机是否按时接单
  - 异常/SOS 优先处理
  - 缺照片要补传
  - 费用未提交要催办

## 涉及文件
- `frontend/src/pages/DriverMonitorPage.tsx`
- `frontend/src/components/PilotFeedbackNote.tsx`

## 验证方式
- `npm.cmd run build`
- 浏览器检查 `#driver-monitor` 页面试运营提示可见。

## 是否完成
DONE

## 风险
- 本轮没有改小程序司机端交互，只处理调度端试运营观察面板。
