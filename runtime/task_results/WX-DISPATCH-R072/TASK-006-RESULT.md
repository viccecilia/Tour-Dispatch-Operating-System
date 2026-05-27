# TASK-006 RESULT

## 修改了什么
- 新增 trial SQLite 备份脚本。
- 新增 trial SQLite 恢复脚本。
- 备份目录固定为 `runtime/backups/trial/`。

## 涉及文件
- `scripts/backup_trial_db.py`
- `scripts/restore_trial_db.py`
- `docs/INTERNAL_TEST_DEPLOY_GUIDE.md`

## 验证方式
- `python scripts/backup_trial_db.py`

## 是否完成
DONE

## 风险
- 恢复前应停止后端，避免运行中数据库被覆盖。
