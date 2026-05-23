# R060 MOBILE QUICK DISPATCH

## 修改了什么

- 升级 `miniapp_dispatch/pages/dispatch/` 为移动快速派车 Runtime。
- 未派车订单池改为横向卡片选择。
- 司机快选改为卡片式展示：
  - 在线状态
  - 当前任务
  - 下一空闲时间
  - 距离占位
- 车辆快选改为卡片式展示：
  - 车型
  - 空闲状态
  - 维护风险
  - ETC
  - 座位
- 增加底部固定“一键派车”预览条。
- 派车冲突以移动端可读文案展示。
- 司机新任务通知文案改为正常中文。
- 新增验证脚本：
  - `scripts/verify_mobile_quick_dispatch.py`

## Dispatcher Runtime 状态

- 手机端可执行：选订单 -> 选司机 -> 选车辆 -> 一键派车。
- 派车成功后：
  - 写入 `assignments`
  - 更新订单 `dispatch_status=assigned`
  - 司机端生成 `new_order` 通知
- 派车失败时显示冲突原因。

## Driver Confirmation Runtime

- 本轮完成“司机收到新订单通知”的联动基础。
- 司机确认接单仍使用既有司机端 `confirm_order` 执行状态流转。

## 验证结果

- `python -m compileall backend scripts`：通过。
- `node --check miniapp_dispatch/pages/dispatch/index.js`：通过。
- `node --check miniapp_dispatch/utils/api.js`：通过。
- `python scripts/reset_demo_db.py`：通过。
- `python scripts/verify_mobile_quick_dispatch.py`：通过，验证派车后司机 `new_order` 通知生成。
- `python scripts/verify_dispatch_mobile_runtime.py`：通过。
- `python scripts/health_check.py`：通过。

## 未完成风险

- 距离字段目前是占位/依赖司机位置上报，尚未做真实距离计算。
- 移动端司机/车辆推荐还不是智能评分，只是快速选择。
- 司机确认接单回执已由既有司机端状态流承担，本轮未重做确认 UI。

## 下一轮建议

- R061：移动调度端司机确认回执与状态看板，重点显示已派未确认、司机已确认、临近出发未确认。
