# TASK-002 RESULT

## 修改了什么
- 新增 `scripts/prepare_trial_db.py`，默认生成独立试运营 SQLite，不覆盖当前演示库。
- 试运营库清空订单、派车、草稿、司机报备、通知、审计、异常等事务数据。
- 保留基础租户、用户、组织、司机、车辆、旅行社、地点等基础资料。

## 涉及文件
- scripts/prepare_trial_db.py

## 验证方式
- `python scripts/prepare_trial_db.py --overwrite`

## 是否完成
DONE

## 风险
- 默认 seed 账号仍需在真实试运营前修改密码。
