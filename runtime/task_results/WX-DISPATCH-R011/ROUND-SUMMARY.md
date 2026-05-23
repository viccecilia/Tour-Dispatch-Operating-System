# WX-DISPATCH-R011 Round Summary

## 修改了什么

- 建立 tenants + tenant_id 数据模型。
- 新增 HMAC JWT 登录。
- API 默认要求登录，按 tenant_id 过滤核心业务数据。
- React 前端接入登录页、token、退出、租户展示。
- 新增 auth/tenant 验证脚本和文档。

## 验证结果

- python -m compileall backend scripts：通过。
- python scripts/reset_demo_db.py：通过。
- python scripts/health_check.py：通过。
- python scripts/verify_auth_tenant.py：通过。
- npm.cmd run build：通过。
- npm.cmd run lint：通过。

## 风险

- 当前 JWT secret 默认值仅适合 demo。
- 角色权限仍是基础边界，细粒度 RBAC 后续再做。
- 历史验证脚本需要在后续统一改成登录后调用。
