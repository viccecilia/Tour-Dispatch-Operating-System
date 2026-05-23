# TASK-001 司机端页面结构拆分

## 修改了什么
- 将 `miniapp/pages/driver/index` 从单页堆叠改为五个内部工作区：首页、出入库、任务地图、费用、我的。
- 保留同一个小程序页面路由，避免破坏原有 `driver_id`、缓存、报备和任务加载链路。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`

## 验证方式
- `node --check miniapp/pages/driver/index.js`

## 是否完成
DONE

## 风险
- 本轮未在微信开发者工具里做真机视觉验收，需要人工打开 `pages/driver/index?driver_id=1` 检查五个入口的实际显示。
