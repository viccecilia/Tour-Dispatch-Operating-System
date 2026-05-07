# TASK-001 结果

状态：DONE

修改了什么：

- 完善 `drivers` 表字段，补齐 `updated_at`。
- 完善 `vehicles` 表字段，补齐 `plate_number`、`seat_count`、`updated_at`，兼容旧字段 `plate_no`、`seats`。
- 初始化脚本加入少量司机/车辆种子数据。
- 修正种子逻辑，避免重复初始化后可用司机继续重复增长。
- 提供可用司机、可用车辆查询能力。

涉及文件：

- `backend/db/schema.sql`
- `backend/db/database.py`
- `backend/services/dispatch_service.py`

验证方式：

- `python scripts/init_db.py`
- `python scripts/verify_dispatch_api.py`

是否完成：是

风险：

- 司机和车辆仍是最小基础数据能力，本轮没有实现完整司机/车辆管理 CRUD。
