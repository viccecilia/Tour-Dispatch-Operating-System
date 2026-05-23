# TASK-002 费用提交字段修正

## 修改了什么
- 修正小程序费用提交字段：由 `expense_type` 改为后端实际读取的 `expense_kind`。
- 验证脚本新增代收费用提交，覆盖 `collect / 代收车费 / in_hand`。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `scripts/verify_driver_api.py`

## 验证方式
- `python scripts/verify_driver_api.py`
- 验证输出包含 `collect_report_success: true` 和 `collect_report_visible: true`。

## 是否完成
DONE

## 风险
- 旧的本机缓存如果保存了 `expense_type` 离线任务，可能需要清空小程序本地缓存。
