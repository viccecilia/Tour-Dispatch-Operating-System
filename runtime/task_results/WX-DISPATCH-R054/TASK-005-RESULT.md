# TASK-005 Backup / Restore Validation

## 修改了什么
- 执行数据库备份。
- 停止后端后执行 restore。
- 重启后端并运行 health check。

## 涉及文件
- `scripts/backup_db.py`
- `scripts/restore_db.py`
- `runtime/backups/wx_dispatch_20260521_142010.sqlite3`

## 验证方式
- `python scripts/backup_db.py`
- `python scripts/restore_db.py <backup_file>`
- `python scripts/health_check.py`

## 是否完成
DONE

## 风险
- 恢复验证使用当前 SQLite 备份；正式试运营前建议保留多份异地备份。
