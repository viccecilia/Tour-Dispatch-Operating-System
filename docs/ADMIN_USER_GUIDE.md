# 管理员试运行使用说明

## 启动

Windows：

```bat
start_demo.bat
```

Mac/Linux：

```bash
sh start_demo.sh
```

React Admin Console：

```bash
cd frontend
npm install
npm run dev
```

默认地址：

- Backend: `http://127.0.0.1:18765`
- React Admin Console: `http://127.0.0.1:5173`

## 演示数据重置

```bash
python scripts/reset_demo_db.py
```

重置后固定生成：

- 今日订单
- 未派车订单
- 已派车订单
- 司机和车辆
- parser 草稿
- driver reports

## 备份

```bash
python scripts/backup_db.py
```

备份文件保存到：

```text
runtime/backups/
```

## 恢复

```bash
python scripts/restore_db.py runtime/backups/<backup_file>.sqlite3
```

恢复后建议运行：

```bash
python scripts/health_check.py
```

## 操作日志

关键写操作会写入：

```text
runtime/logs/operations.log
```

记录内容包括：

- 时间
- actor
- HTTP method
- API path
- 简化后的 payload

密码和 token 会被隐藏。

## 角色边界

- `admin`: 可登录管理端。
- `dispatcher`: 可登录管理端进行录单和派车。
- `driver`: 不允许登录管理端；司机端通过 `driver_id` / `X-Driver-Id` 使用。

本轮没有接正式微信登录，也没有复杂权限系统。
