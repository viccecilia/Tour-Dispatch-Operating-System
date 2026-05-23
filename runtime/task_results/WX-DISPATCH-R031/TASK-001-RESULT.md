# TASK-001 司机今日任务页

## 修改了什么
- 小程序司机端改为清晰中文的今日任务页。
- 默认只保留当天任务，按开始时间排序。
- 当前进行中任务置顶，已完成/已归库任务折叠到下方。
- 当前订单卡片展示时间、起点、终点、客人、联系方式、车辆和状态。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`

## 验证方式
- `node --check miniapp/pages/driver/index.js`
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 小程序视觉和微信定位授权仍需要在微信开发者工具/真机中人工确认。
