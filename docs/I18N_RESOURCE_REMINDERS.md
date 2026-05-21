# R032 中文化、多语言基础与到期提醒说明

## 多语言基础

- React Console 新增 `frontend/src/i18n/dictionaries.ts`，默认语言为 `zh-CN`。
- React Console 新增 `frontend/src/stores/languageStore.ts`，语言选择保存在浏览器 `localStorage`。
- 小程序新增 `miniapp/utils/i18n.js`，预留 `zh-CN`、`ja-JP`、`en-US` 字典结构。
- 当前完整维护中文主文案，日文和英文先作为 key 结构预留。

## 车辆提醒字段

- `last_inspection_date`：最近三个月点检日期。
- `next_inspection_due_date`：下次点检到期日。
- `shaken_due_date`：一年车检到期日。
- `insurance_due_date`：保险到期日，当前展示为预留信息。
- `maintenance_status`：维修状态或备注。

## 司机提醒字段

- `license_due_date`：驾照到期日。
- `health_check_due_date`：健康体检到期日。
- `driver_status`：司机状态扩展字段，兼容旧 `status` 字段。

## 提醒规则

规则保存到 `settings` 表，key 为 `resource_reminder_rules`：

- 车辆点检默认提前 20 天。
- 车辆车检默认提前 20 天。
- 司机体检默认提前 30 天。
- 驾照到期默认提前 30 天。

React 车辆/司机管理页可以修改提醒天数。提醒结果会进入：

- Dashboard `resource_alerts`
- `/api/resources/reminders`
- `/api/notifications`
- React 车辆/司机管理页提醒中心

## 兼容说明

为避免破坏 R001-R031 主链路，后端保留旧字段别名：

- `license_expires_at` -> `license_due_date`
- `medical_check_expires_at` -> `health_check_due_date`
- `inspection_expires_at` -> `next_inspection_due_date`
- `insurance_expires_at` -> `insurance_due_date`

派车链路仍使用旧的 `status = available/busy/maintenance/inactive` 判断可用资源。
