# wx_dispatch_platform

轻量微信小程序调度平台 MVP。

当前项目已经具备：

- 后端 API：登录、订单、草稿解析、派车、日历、司机报备、dashboard。
- 本地数据库：SQLite，默认文件 `runtime/wx_dispatch.sqlite3`。
- 调度台：`/dashboard`，用于电脑端演示和运营验收。
- 小程序端：`miniapp/`，用于微信开发者工具预览。
- 演示数据：通过 `scripts/reset_demo_db.py` 一键重置为稳定演示库。

快速启动：

```bash
python scripts/reset_demo_db.py
python backend/main.py
```

默认地址：

- 后端 API：`http://127.0.0.1:8000`
- 调度台：`http://127.0.0.1:8000/dashboard`

如果 8000 端口被占用：

```bash
$env:WX_DISPATCH_PORT='18765'
python backend/main.py
```

更多步骤见：

- `docs/STARTUP_GUIDE.md`
- `docs/BOSS_DEMO_SCRIPT.md`
- `docs/MINIAPP_MANUAL_CHECKLIST.md`
