# TASK-001：本地缓存与离线队列

## 修改了什么
- 新增司机端离线队列工具。
- 报备、手动位置上报、实时位置上报失败时都会保存到本机队列。
- 队列记录包含类型、payload、创建时间、重试次数和最近错误。

## 涉及文件
- `miniapp/utils/offlineQueue.js`
- `miniapp/pages/driver/index.js`

## 验证方式
- `node --check miniapp/utils/offlineQueue.js`
- `node --check miniapp/pages/driver/index.js`

## 是否完成
DONE

## 风险
- 队列保存在微信本地 storage，卸载小程序或清理缓存会丢失。
