# TASK-002 手机号注册绑定与登录

- 状态：DONE
- 修改：新增手机号登录、预录手机号注册绑定、司机/管理人员 profile 绑定、密码重置为手机号后 6 位。
- 涉及文件：`backend/services/auth_service.py`, `backend/api/routes.py`
- 验证：`python scripts/verify_auth_roles.py`
- 风险：非司机角色需要先存在带手机号的 `operator_profiles` 预录资料。
