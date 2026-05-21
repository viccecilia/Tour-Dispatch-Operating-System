# 故障恢复说明

## 后端无法访问

现象：

- React 顶部显示 `API offline`
- `python scripts/health_check.py` 失败

处理：

1. 检查端口：

```powershell
netstat -ano | Select-String ":18765"
```

2. 重启后端：

```bash
python backend/main.py
```

3. 再次检查：

```bash
python scripts/health_check.py
```

## 数据混乱或演示数据累加

处理：

```bash
python scripts/reset_demo_db.py
```

## 数据库损坏或误删

1. 找到最近备份：

```text
runtime/backups/
```

2. 恢复：

```bash
python scripts/restore_db.py runtime/backups/<backup_file>.sqlite3
```

3. 验证：

```bash
python scripts/health_check.py
```

## 前端打不开

处理：

```bash
cd frontend
npm install
npm run dev
```

默认打开：

```text
http://127.0.0.1:5173
```

## 真实订单解析异常

原则：

- 失败不丢原文。
- 先人工编辑草稿。
- 再确认入库。

如果同类文本多次失败，把原文样本保存给管理员，用于扩展规则库。
