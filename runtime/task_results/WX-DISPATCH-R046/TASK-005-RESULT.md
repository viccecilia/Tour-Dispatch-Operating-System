# TASK-005 Google Maps fallback

## 修改了什么
- 无坐标时显示“暂无坐标，请使用文字地址导航”。
- 自动生成 Google Maps URL：
  `https://www.google.com/maps/search/?api=1&query=...`
- 支持复制导航 URL 到剪贴板。

## 涉及文件
- `miniapp/pages/driver/index.js`

## 验证方式
- `node --check miniapp/pages/driver/index.js`

## 是否完成
DONE

## 风险
- 不接 Google Maps JS SDK；小程序内只做 URL fallback 和复制。
