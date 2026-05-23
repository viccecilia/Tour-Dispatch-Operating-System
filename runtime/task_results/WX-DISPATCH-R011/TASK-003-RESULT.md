# TASK-003 Tenant API Isolation

- 修改了什么：API 除 ping/login 外要求登录；orders/drafts/dispatch/calendar/dashboard/resources/driver 数据按 tenant_id 查询。
- 涉及文件：backend/api/routes.py, backend/services/order_service.py, backend/services/parser_service.py, backend/services/dispatch_service.py, backend/services/calendar_service.py, backend/services/dashboard_service.py, backend/services/resource_service.py, backend/services/driver_service.py。
- 验证方式：python scripts/verify_auth_tenant.py 确认 tenant2 看不到 admin 创建订单。
- 是否完成：DONE。
- 风险：finance/operation log 仍是轻量实现，后续权限矩阵需要继续收口。
