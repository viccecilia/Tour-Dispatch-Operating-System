# TASK-003 角色权限边界

- 状态：DONE
- 修改：新增 `operations_manager`，财务 API 限制为 admin，司机 token 强制使用自身 profile。
- 涉及文件：`backend/services/org_service.py`, `backend/api/routes.py`, `backend/services/auth_service.py`
- 验证：`python scripts/verify_auth_roles.py`, `python scripts/verify_finance_ledger.py`
- 风险：旧的演示接口仍保留无 token 的 `driver_id` 兼容路径；带 driver token 时会强制绑定本人。
