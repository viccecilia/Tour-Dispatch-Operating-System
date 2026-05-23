# TASK-002 司机实时位置上报

## 修改了什么
- 小程序司机端保留状态报备时自动携带位置。
- 新增“开启实时位置 / 关闭实时位置”按钮。
- 开启后每 30 秒调用微信定位并写入位置日志。
- 支持手动“上报当前位置”。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`
- `backend/services/driver_service.py`

## 验证方式
- `node --check miniapp/pages/driver/index.js`
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 持续定位需要微信开发者工具或真机授权验证；本地只能验证 API 写入链路。
