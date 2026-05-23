# TASK-003：小程序司机通知中心

## 修改了什么
- 司机端今日任务页增加通知卡片。
- 显示未读数量、通知标题、正文、类型、时间和已读状态。
- 点击通知可标记已读并刷新。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`
- `miniapp/utils/api.js`

## 验证方式
- `node --check miniapp/pages/driver/index.js`

## 是否完成
DONE

## 风险
- 小程序页面需要在微信开发者工具或真机中人工确认视觉和点击体验。
