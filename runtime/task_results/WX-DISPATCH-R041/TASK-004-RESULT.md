# TASK-004 照片节点与执行证据

## 修改了什么
- 扩展司机照片类型：到达等待、接客/出发、途中地点、送达、车辆点检、清扫、费用小票。
- 小程序端提供照片节点按钮。
- 后端保存 mock/本地上传路径，照片关联 driver、assignment、order、photo_type、note。

## 涉及文件
- `backend/services/driver_service.py`
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `scripts/verify_driver_api.py`

## 验证方式
- `python scripts/verify_driver_api.py` 验证 evidence 上传和查询。

## 是否完成
DONE

## 风险
- 当前仍是本地上传目录，不是正式云存储；真机上传体验需要微信开发者工具/手机验证。
