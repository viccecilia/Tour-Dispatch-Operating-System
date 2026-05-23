# TASK-002 JWT Login

- 修改了什么：替换旧内存 token 为 HMAC JWT，token 内包含 user/role/tenant_id。
- 涉及文件：backend/services/auth_service.py, backend/config.py, backend/app/config.py。
- 验证方式：python scripts/verify_auth_tenant.py。
- 是否完成：DONE。
- 风险：JWT secret 当前有 demo 默认值，正式部署必须配置 WX_DISPATCH_JWT_SECRET。
