# TASK-005 Validation

- 修改了什么：新增 auth/tenant 验证脚本，health_check 支持登录后检查受保护 API。
- 涉及文件：scripts/verify_auth_tenant.py, scripts/health_check.py。
- 验证方式：python scripts/verify_auth_tenant.py；python scripts/health_check.py。
- 是否完成：DONE。
- 风险：历史 verify_* 脚本未全部改造为 JWT，本轮必跑项已覆盖。
