# WX-DISPATCH-R030 ROUND SUMMARY

## Round Name
Pilot Launch Version

## 完成内容
- 冻结试运营范围，不新增业务模块。
- 新增安全的试运营数据库准备脚本，默认生成独立 trial DB。
- 新增用户手册、培训指南、发布检查清单、试运营启动说明。
- 修复 `verify_orders_api.py` 与 `verify_calendar_api.py` 未携带登录 token 的回归验证问题。
- 执行 health、orders、dispatch、calendar、parser、driver、auth tenant、frontend build 全链路验证。

## 验证结论
全链路脚本通过，前端构建通过，试运营数据库可生成。

## 风险
- 当前运行库被 smoke 脚本写入了测试订单/草稿/派车记录；真实试运营应切换到 `runtime/trial/wx_dispatch_trial.sqlite3` 或重新生成试运营库。
- 真实用户试运营前需要人工确认账号密码、员工培训、备份恢复和回滚流程。
- 当前角色权限仍是 MVP 级别，不是完整企业级 RBAC。
