# TASK-002：司机位置上报

## 修改了什么
- 新增 `POST /api/driver/location`。
- 司机报备时自动同步写入位置日志。
- 小程序司机端新增“上报当前位置”按钮，支持手机定位，定位失败时上报手动位置文字。

## 涉及文件
- `backend/services/driver_service.py`
- `backend/api/routes.py`
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`
- `miniapp/utils/api.js`

## 验证方式
- 位置 smoke：`location_success = true`，返回 `location_id`。
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 真机定位权限需要微信开发者工具和手机端人工确认。
