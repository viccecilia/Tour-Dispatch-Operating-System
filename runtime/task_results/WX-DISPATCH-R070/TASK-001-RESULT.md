# TASK-001 账号字段与角色扩展

- 状态：DONE
- 修改：扩展 `users` schema，新增手机号、profile 绑定、微信绑定、登录时间和密码更新时间字段。
- 涉及文件：`backend/db/schema.sql`, `backend/db/database.py`
- 验证：`python -m compileall backend scripts`
- 风险：SQLite role CHECK 已通过兼容迁移处理，旧库需要运行初始化或 reset 脚本触发迁移。
