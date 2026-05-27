# TASK-006 验证脚本

- 状态：DONE
- 修改：新增 `scripts/verify_auth_roles.py`，覆盖手机号注册、角色权限、微信绑定和密码重置。
- 涉及文件：`scripts/verify_auth_roles.py`
- 验证：脚本已运行通过。
- 风险：脚本会创建 R070 验证账号和司机样本，用于权限回归验证。
