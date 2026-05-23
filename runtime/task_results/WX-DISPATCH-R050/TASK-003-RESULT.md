# TASK-003：通知中心页面

## 修改了什么
- 新增 React 运营提醒中心页面。
- 新增左侧导航入口。
- 页面展示：
  - 未读提醒
  - 高优先级提醒
  - 提醒总数
  - 提醒列表
  - 标记已读
  - 全部已读

## 涉及文件
- `frontend/src/pages/NotificationsPage.tsx`
- `frontend/src/app/App.tsx`
- `frontend/src/layouts/SaasShell.tsx`
- `frontend/src/stores/navigationStore.ts`

## 验证方式
- `npm.cmd run build`
- `npm.cmd run lint`

## 是否完成
- DONE

## 风险
- 页面为系统内通知中心，不做短信、LINE、微信正式推送。
