# 手机号账号绑定与角色权限规则

## 账号绑定

- 用户账号保存在 `users`。
- 司机资料保存在 `drivers`，司机注册时必须匹配已录入的 `drivers.phone`。
- 调度、运行管理、管理账号通过 `operator_profiles.phone` 匹配后台预录资料。
- 登录账号通过 `profile_type` 和 `profile_id` 绑定到真实人员资料。

## 角色

- `admin`：全部权限，包含财务。
- `dispatcher`：订单、解析、派车、日历、司机状态。
- `operations_manager`：车辆、司机、出勤、证件、保养、地图、运行异常。
- `driver`：自己的任务、出入库、报备、费用上报、个人资料。

## 财务边界

- 财务 API 仅允许 `admin`。
- `dispatcher` 和 `operations_manager` 不能访问财务 API。
- 司机端不返回订单销售价格和财务结算金额。

## 微信双重绑定

- 微信小程序登录传入 `wx_openid`。
- 首次登录时绑定当前微信。
- 后续登录必须使用同一微信，否则返回 `wechat_binding_mismatch`。
- React Web 后台暂不强制微信绑定。
- 管理员可解除微信绑定，用户下次小程序登录时重新绑定。

## 密码重置

- 管理员可将密码重置为手机号后 4 位。
- 重置、解绑微信、注册绑定、微信绑定失败均写入审计。
