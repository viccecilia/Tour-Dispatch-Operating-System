# WX-DISPATCH-R070 Round Summary

## 状态

- TASK-001：DONE
- TASK-002：DONE
- TASK-003：DONE
- TASK-004：DONE
- TASK-005：DONE
- TASK-006：DONE

## 核心结果

- 手机号账号体系可用。
- 已录入手机号才能注册/绑定。
- 角色包含 `admin / dispatcher / operations_manager / driver`。
- 财务 API 仅 admin 可访问。
- 运行管理可访问车辆、司机、地图等运行数据，但不能访问财务。
- 司机 token 会强制绑定到自己的 driver profile。
- 小程序端支持微信 openid 双重绑定，不同微信登录同一账号会被拒绝。
- 管理员可解除微信绑定。
- 密码可重置为手机号后 6 位。

## 验证

- `python -m compileall backend scripts`
- `python scripts/reset_demo_db.py`
- `python scripts/health_check.py`
- `python scripts/verify_auth_roles.py`
- `python scripts/verify_driver_api.py`
- `python scripts/verify_dispatch_api.py`
- `python scripts/verify_finance_ledger.py`

## 风险

- 本轮未接微信正式授权，使用 mock openid 预留。
- 管理端账号卡片 UI 留到 R071。
- 旧司机端演示接口仍兼容 `driver_id` 参数；带 driver token 时已强制只能访问本人。
