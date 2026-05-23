# TASK-003 派车页视觉升级

## 修改了什么
- 保留“导入 + 待派订单池 + 司机/车辆选择 + 一键派车”链路。
- 清理乱码文案，恢复中文展示。
- 订单池改成白底大圆角卡片，问题订单用柔和风险提示。
- 司机/车辆列表改为简洁资源卡片。
- 底部派车条改为白底轻阴影移动操作条。
- 修复 `dispatch/index.js` 中被乱码破坏的字符串，保证页面 JS 可执行。

## 涉及文件
- `miniapp_dispatch/pages/dispatch/index.js`
- `miniapp_dispatch/pages/dispatch/index.wxml`
- `miniapp_dispatch/pages/dispatch/index.wxss`

## 验证方式
- `node --check miniapp_dispatch/pages/dispatch/index.js`

## 是否完成
DONE

## 风险
- 高订单量下真实滚动效率仍需在微信开发者工具和真机上人工确认。
