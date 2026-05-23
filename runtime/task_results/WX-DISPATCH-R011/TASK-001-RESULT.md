# TASK-001 Auth & Tenant Schema

- 修改了什么：新增 tenants 表、users.tenant_id、核心业务表 tenant_id 兼容迁移。
- 涉及文件：backend/db/schema.sql, backend/db/database.py, backend/services/tenant_context.py。
- 验证方式：python -m compileall backend scripts；python scripts/reset_demo_db.py。
- 是否完成：DONE。
- 风险：旧 SQLite 通过 ALTER TABLE 迁移，正式环境上线前仍需备份。
