# TASK-002：司机确认接单

## 修改了什么
- 沿用现有 `POST /api/driver/report` 的 `confirm_order` 动作。
- `assigned -> confirmed` 作为司机确认接单状态，不新增混乱状态。
- 司机首页可从“明日订单”点选订单，再使用底部主按钮确认接单。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `scripts/verify_dispatch_api.py`

## 验证方式
- `python scripts/verify_dispatch_api.py`
- 验证项：`driver_confirm_success = true`
- `python scripts/verify_driver_api.py`
- 验证项：状态流包含 `confirmed`

## 是否完成
DONE

## 风险
- 真机上仍需人工确认“明日订单 -> 底部确认接单”是否足够醒目。
