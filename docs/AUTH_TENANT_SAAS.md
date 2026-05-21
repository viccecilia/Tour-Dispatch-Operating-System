# Auth & Multi-Tenant SaaS

## 登录

- `POST /api/auth/login`
- Demo admin: `admin / admin123`
- Demo tenant 2 admin: `tenant2_admin / admin123`

登录成功返回 HMAC JWT token。前端保存到 `localStorage.wx_dispatch_token`，后续 API 自动带：

```text
Authorization: Bearer <token>
```

## 租户

新增 `tenants` 表，`users` 绑定 `tenant_id`。核心业务表增加 `tenant_id`，现有 demo 数据默认归属 tenant `1`。

第一版租户隔离覆盖：

- users
- agencies
- locations
- drivers
- vehicles
- orders
- assignments
- order_drafts
- driver_reports

## API 访问规则

- `/api/ping` 允许匿名，用于 health check。
- `/api/auth/login` 允许匿名。
- 其他 `/api/*` 需要 JWT。
- 后端根据 JWT 中的 `tenant_id` 设置当前请求上下文，服务层按 tenant 查询和写入。

## 当前边界

- JWT 使用内置 HMAC SHA256，适合 demo/runtime，不是最终企业 SSO。
- 角色已进入 token 和前端显示，但细粒度 RBAC 只做基础边界，后续再拆权限矩阵。
