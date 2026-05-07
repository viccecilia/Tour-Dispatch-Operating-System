# TASK-004 结果

状态：DONE

完成内容：

- `users.role` 支持 `admin`、`dispatcher`、`driver`。
- 本轮仅允许 `admin` 账号通过 `/api/auth/login` 登录。
- 登录成功返回 token 和用户信息。
- `/api/auth/me` 支持通过 `Authorization: Bearer <token>` 获取当前用户。

默认管理员：

- username：`admin`
- password：`admin123`
- role：`admin`
