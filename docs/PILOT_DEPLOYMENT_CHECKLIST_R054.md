# WX-DISPATCH-R054 部署检查清单

## 启动前

- 确认 `.env` 或环境变量中的端口和数据库路径正确。
- 确认 `runtime/wx_dispatch.sqlite3` 存在。
- 确认已执行一次数据库备份。
- 确认微信开发者工具小程序 API 地址指向当前后端。

## 启动

```bash
python backend/main.py
```

或使用项目已有启动脚本：

```bash
start_demo.bat
```

## 验证

- 打开 React Console。
- 打开后端 dashboard。
- 打开微信开发者工具司机端。
- 执行 `python scripts/health_check.py`。

## 备份

```bash
python scripts/backup_db.py
```

备份文件应出现在：

```text
runtime/backups/
```

## 恢复

恢复前建议停止后端服务。

```bash
python scripts/restore_db.py runtime/backups/<backup_file>.sqlite3
python scripts/health_check.py
```

## 回滚

- 停止后端。
- 使用最近一次稳定备份执行 restore。
- 重启后端。
- 重新运行 health check 和核心验证脚本。

## 人工验收

- 调度员：Parser -> Orders -> Dispatch -> Calendar。
- 司机：接单 -> 出库 -> 执行订单 -> 上传照片 -> 费用报备 -> 入库。
- 财务：查看订单台账 -> 确认费用 -> 导出。
