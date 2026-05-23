# TASK-004：任务地图页导航化

## 修改了什么
- 当前订单卡移动到地图上方，路线、时间、状态更突出。
- 地图区域加高，强化真实导航入口感。
- 导航按钮改为大按钮：去上车点、去终点。
- 保留微信 `map`、当前位置上报、`openLocation` 和文字地址 fallback 逻辑。

## 涉及文件
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`

## 验证方式
- `node --check miniapp/pages/driver/index.js`
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 地图组件、定位授权、`openLocation` 需要在微信开发者工具或真机上人工确认。
