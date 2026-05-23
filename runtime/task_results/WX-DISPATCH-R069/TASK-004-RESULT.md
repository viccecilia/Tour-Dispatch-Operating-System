# TASK-004 地图页视觉升级

## 修改了什么
- 地图页改为地图主视觉。
- 顶部浮层保留搜索、司机/订单切换和轻量状态统计。
- 底部浮层显示司机或订单结果列表。
- 清理乱码文案，修复 map 页面 JS 字符串。

## 涉及文件
- `miniapp_dispatch/pages/map/index.js`
- `miniapp_dispatch/pages/map/index.wxml`
- `miniapp_dispatch/pages/map/index.wxss`

## 验证方式
- `node --check miniapp_dispatch/pages/map/index.js`

## 是否完成
DONE

## 风险
- 本轮不新增地图 SDK，也不做复杂地图能力；地图数据仍依赖已有位置接口。
