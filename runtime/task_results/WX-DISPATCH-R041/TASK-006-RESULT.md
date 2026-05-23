# TASK-006 地图与导航卡片

## 修改了什么
- 小程序司机端增加地图与位置卡片。
- 支持 `wx.getLocation` 上报当前位置。
- 支持导航到上车点/终点。
- 无目的地坐标时提示复制文字地址，并预留 Google Maps URL。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`
- `miniapp/utils/api.js`
- `backend/services/driver_service.py`

## 验证方式
- `python scripts/verify_driver_api.py` 验证位置上报和 latest location。
- 真机导航需人工验证。

## 是否完成
DONE

## 风险
- 未接真实地址转坐标；当前导航在没有目的地坐标时走文字地址/Google Maps URL 预留。
