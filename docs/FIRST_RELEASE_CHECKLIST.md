# 首版试运行发布清单

## 发布前必须确认

- [ ] `python scripts/reset_demo_db.py` 可运行。
- [ ] `python scripts/health_check.py` 全部 `[OK]`。
- [ ] React Admin Console 可打开。
- [ ] Parser 可批量粘贴订单。
- [ ] 草稿可编辑并确认入库。
- [ ] Orders 可看到确认后的订单。
- [ ] Dispatch 可批量派车。
- [ ] Calendar 可看到派车结果。
- [ ] Driver Monitor 可看到司机状态。
- [ ] 司机端 API 可状态回传。
- [ ] Dashboard 统计可信。
- [ ] `python scripts/backup_db.py` 可备份。
- [ ] `python scripts/restore_db.py <backup>` 可恢复。
- [ ] `runtime/logs/operations.log` 有操作日志。
- [ ] 员工已阅读 `docs/EMPLOYEE_USER_GUIDE.md`。
- [ ] 管理员已阅读 `docs/ADMIN_USER_GUIDE.md`。
- [ ] 故障恢复负责人知道 `docs/FAULT_RECOVERY_GUIDE.md`。

## 本轮验证结论

R015 已完成：

- 120 单真实格式压测。
- parser / orders / dispatch / calendar / driver / dashboard 回归。
- 备份恢复演练。
- 服务重启演练。
- 前端 build / lint。
- 后端 health check。

## 进入试运行条件

满足以下条件即可进入第一版试运行：

- 老板演示通过。
- 调度员录单验收通过。
- 调度员派车验收通过。
- 司机端执行验收通过。
- 管理员备份恢复验收通过。

## 首版限制

- 不含正式微信登录。
- 不含地图。
- 不含 WebSocket 实时推送。
- 不含复杂财务结算。
- 不含复杂权限系统。
