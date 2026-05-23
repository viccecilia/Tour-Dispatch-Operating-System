# TASK-004 微信地图与导航

## 修改了什么
- 微信 `map` 组件绑定 `markers` 和 `show-location`。
- 地图 marker 支持当前位置、上车点、终点。
- 获取定位后刷新地图中心和当前位置 marker。
- `wx.openLocation` 只在订单目的地有坐标时使用。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`

## 验证方式
- `python scripts/verify_driver_api.py`
- 验证输出包含 `manual_location_success: true`、`latest_location_visible: true`。

## 是否完成
DONE

## 风险
- 真实上车点/终点 marker 依赖订单坐标字段；无坐标时只显示当前位置和文字地址。
