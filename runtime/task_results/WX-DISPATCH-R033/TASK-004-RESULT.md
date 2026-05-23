# TASK-004 司机端展示

## 修改了什么
- 小程序司机端加载任务时同时请求司机收入。
- 顶部今日收入改为使用收入 API。
- 新增收入与结算区域，明确说明司机端不显示订单价格。

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
- 微信小程序页面需要在开发者工具或真机确认视觉效果。
