# TASK-003 微信位置上报与一键导航

## 修改了什么
- 状态报备时尝试调用微信定位，并把 latitude、longitude、location_text 一起提交。
- 增加手动“上报当前位置”。
- 增加导航到上车点、导航到终点入口。
- 没有坐标时不报错，提示复制文本地址到导航软件。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `backend/services/driver_service.py`

## 验证方式
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- `wx.getLocation` 和 `wx.openLocation` 依赖微信权限与真机环境，本地只能验证接口链路。
