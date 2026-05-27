# TASK-005 审计与文档

- 状态：DONE
- 修改：注册绑定、登录失败、微信绑定、微信冲突、解绑、密码重置写入审计；新增账号规则文档。
- 涉及文件：`backend/services/auth_service.py`, `docs/AUTH_ROLE_BINDING_RULES.md`
- 验证：`python scripts/verify_auth_roles.py`
- 风险：审计中不记录密码和 token，微信 openid 不返回给前端公开用户对象。
