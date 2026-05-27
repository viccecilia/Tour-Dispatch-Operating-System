# Internal Test Deploy Guide

本指南用于把 Tour Dispatch Operating System 部署到云端 trial 环境，供微信小程序体验版和 Web 管理后台内部测试使用。

## 1. 云服务器准备

- Python 3.10+
- Node.js 18+
- 一个 HTTPS API 域名，例如 `https://api.example.com`
- 一个 HTTPS Web 管理后台域名，例如 `https://admin.example.com`
- 服务器防火墙放行后端端口，例如 `18765`

## 2. Trial 环境配置

复制配置文件：

```bash
cp .env.trial.example .env.trial
```

修改：

```text
WX_DISPATCH_HOST=0.0.0.0
WX_DISPATCH_PORT=18765
WX_DISPATCH_BASE_URL=https://api.example.com
WX_DISPATCH_DB=runtime/trial/wx_dispatch_trial.sqlite3
WX_DISPATCH_DEMO_MODE=false
WX_DISPATCH_TRIAL_MODE=true
WX_DISPATCH_RESET_DEMO_ON_START=false
WX_DISPATCH_SUPER_WECHAT_IDS=zongzou
```

注意：trial 环境禁止自动 reset demo 数据，避免内部测试数据被启动脚本清空。

## 3. 初始化 Trial 数据库

```bash
python scripts/init_trial_db.py --reset
```

脚本会：

- 初始化 trial SQLite 表结构
- 清空订单、派车、草稿、报备等交易数据
- 保留真实司机、真实车辆、旅行社和地点库
- 创建内部测试账号
- 保留超级微信测试号 `zongzou`

默认账号：

| 角色 | 账号 | 密码 |
| --- | --- | --- |
| 管理员 | admin | admin123 |
| 调度 | 090-72-0001 | 0001 |
| 运行管理 | 090-73-0001 | 0001 |
| 司机 | 司机手机号数字 | 手机号后 4 位 |

## 4. 启动后端 API

Linux/macOS:

```bash
WX_DISPATCH_ENV=trial python backend/main.py
```

Windows PowerShell:

```powershell
$env:WX_DISPATCH_ENV="trial"
python backend/main.py
```

后端必须监听 `0.0.0.0`，云服务器外部访问通过 HTTPS 反向代理到该端口。

检查：

```bash
curl https://api.example.com/api/ping
```

## 5. 部署 React Web 管理后台

```bash
cd frontend
set VITE_API_BASE_URL=https://api.example.com
npm install
npm run build
```

将 `frontend/dist/` 部署到静态站点服务，并绑定：

```text
https://admin.example.com
```

## 6. 微信小程序 API 地址

司机小程序和调度小程序的 API 地址由 `miniapp/utils/api.js` 与 `miniapp_dispatch/utils/api.js` 集中管理。

本地开发默认：

```text
http://localhost:18765
```

体验版必须切换为：

```text
https://api.example.com
```

可以在代码中调用：

```js
api.setBaseUrl('https://api.example.com')
```

## 7. 微信开发者后台合法域名

必须在微信公众平台配置：

- request 合法域名：`https://api.example.com`
- uploadFile 合法域名：`https://api.example.com`
- downloadFile 合法域名：`https://api.example.com`

微信体验版和真机测试必须使用 HTTPS 域名，不能使用 `127.0.0.1` 或局域网 IP。

## 8. 上传体验版

1. 微信开发者工具打开 `miniapp/`
2. 确认 API 地址为 HTTPS trial 域名
3. 点击上传
4. 微信公众平台设置体验版
5. 添加体验成员
6. 真机扫码测试

调度小程序同理，打开 `miniapp_dispatch/`。

## 9. 备份与恢复

备份：

```bash
python scripts/backup_trial_db.py
```

恢复：

```bash
python scripts/restore_trial_db.py runtime/backups/trial/<backup>.sqlite3
```

## 10. Health Check

```bash
python scripts/health_check_trial.py
```

可选设置：

```bash
WX_DISPATCH_TRIAL_BASE_URL=https://api.example.com
WX_DISPATCH_WEB_URL=https://admin.example.com
```

## 常见问题

- `request 合法域名错误`：微信后台未配置 HTTPS API 域名。
- `connection refused`：后端未启动、端口未放行或反向代理未配置。
- `401 Unauthorized`：账号未登录、token 过期或角色权限不匹配。
- `司机看不到订单`：确认派车 assignment 的 driver_id 与司机账号绑定的 profile_id 一致。
- `trial 数据丢失`：检查是否误用了 demo reset 脚本，trial 环境不要设置 `WX_DISPATCH_RESET_DEMO_ON_START=true`。
