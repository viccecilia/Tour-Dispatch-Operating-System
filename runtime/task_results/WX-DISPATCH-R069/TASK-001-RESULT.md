# TASK-001 统一调度小程序视觉 Token

## 修改了什么
- 重建 `miniapp_dispatch/app.wxss` 的全局视觉 token。
- 统一主色、背景色、圆角、轻阴影、卡片、按钮、输入框、badge、空状态。

## 涉及文件
- `miniapp_dispatch/app.wxss`

## 验证方式
- `node --check` 覆盖页面 JS。
- 微信开发者工具需人工确认样式实际渲染。

## 是否完成
DONE

## 风险
- 仅完成视觉 token 统一，不包含复杂设计组件库。
