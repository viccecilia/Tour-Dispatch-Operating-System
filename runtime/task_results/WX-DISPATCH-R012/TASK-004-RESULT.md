# TASK-004 Verification Script Auth Fix

- 修改了什么：R011 后 API 需要 JWT，本轮把 dispatch/driver 验证脚本改成登录后带 Authorization。
- 涉及文件：scripts/verify_dispatch_api.py, scripts/verify_driver_api.py。
- 验证方式：两个脚本均运行通过。
- 是否完成：DONE。
- 风险：其他历史 verify 脚本后续也应统一接入登录 token。
