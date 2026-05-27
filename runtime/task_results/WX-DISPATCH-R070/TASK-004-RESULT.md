# TASK-004 微信双重绑定

- 状态：DONE
- 修改：小程序端登录支持 `wx_openid`，首次绑定微信，不同微信登录返回 `wechat_binding_mismatch`，管理员可解绑。
- 涉及文件：`backend/services/auth_service.py`, `backend/api/routes.py`, `miniapp/utils/api.js`, `miniapp_dispatch/utils/api.js`
- 验证：`python scripts/verify_auth_roles.py`
- 风险：本轮使用 mock openid，未接微信正式授权。
