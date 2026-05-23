# TASK-005 Notification 调整

## 修改了什么
- Notifications 页面顶部增加提醒试运营规则：
  - 高优先级先处理
  - 处理后标记已读
  - 观察是否过度提醒
  - 记录误报和漏报

## 涉及文件
- `frontend/src/pages/NotificationsPage.tsx`
- `frontend/src/components/PilotFeedbackNote.tsx`

## 验证方式
- `npm.cmd run build`
- 浏览器检查 `#notifications` 页面试运营提示可见。

## 是否完成
DONE

## 风险
- 本轮没有改通知生成频率，只给真实试运营提供记录和处理规范入口。
