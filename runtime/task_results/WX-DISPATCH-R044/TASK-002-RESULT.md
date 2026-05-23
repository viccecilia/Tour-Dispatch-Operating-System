# TASK-002 地图卡片与导航入口

## 修改了什么
- 任务地图页新增地图与导航卡片。
- 显示当前位置、上车点、终点。
- 保留上报当前位置、导航到上车点、导航到终点、文字地址 fallback。

## 涉及文件
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxss`

## 验证方式
- `python scripts/verify_driver_api.py`
- 验证输出包含 `manual_location_success: true`、`latest_location_visible: true`。

## 是否完成
DONE

## 风险
- 本轮不接复杂 Google SDK，不做实时轨迹；无坐标时仍使用文字地址导航。
