# TASK-001 结果

## 修改了什么

新增 `scripts/reset_demo_db.py`，支持一键重置演示数据库。

脚本流程：

1. 优先删除旧 SQLite 文件。
2. 如果数据库文件被运行中的后端锁定，则自动降级为库内清表重置。
3. 调用 `init_db(seed=True)` 重建基础表结构。
4. 调用 `demo_seed.main()` 写入固定演示数据。
5. 输出关键表数量。

## 涉及文件

- `scripts/reset_demo_db.py`

## 验证方式

运行：

```bash
python scripts/reset_demo_db.py
```

结果：

- orders: 40
- assignments: 30
- drivers: 10
- vehicles: 8
- agencies: 5
- order_drafts: 5
- driver_reports: 48

## 是否完成

DONE

## 风险

如果后端正在运行，SQLite 文件可能无法删除；脚本已处理为库内重置，但仍建议演示前先停止旧服务或确认只运行一个后端。
