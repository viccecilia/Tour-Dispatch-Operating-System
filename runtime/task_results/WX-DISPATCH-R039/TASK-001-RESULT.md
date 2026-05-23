# TASK-001：司机 SOS 与异常报备

## 修改了什么
- 新增司机安全事件提交能力。
- 支持 `sos`、车辆异常、客人异常、延误报备、其他异常。
- 司机提交后写入 `incidents`，并触发现有通知机制给调度端。

## 涉及文件
- `backend/services/driver_service.py`
- `backend/api/routes.py`
- `miniapp/utils/api.js`
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`

## 验证方式
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 本轮不做复杂安防系统，SOS 是系统内高优先级异常，不接短信或电话。
