# TourFlow Trial Deploy Guardrails

每次上传到云端后，必须先做这一组检查，再让用户测试。

## 高频重复错误

1. Web 构建包把 API 指到 `admin-trial.taxi-airport.jp` 或 `127.0.0.1:18765`，导致云端登录 405/404/连接失败。
2. 云端 API 没有以 `WX_DISPATCH_ENV=trial` 启动，数据库写到 `runtime/wx_dispatch.sqlite3`，而不是 `runtime/trial/wx_dispatch_trial.sqlite3`。
3. 测试账号 seed 写错数据库，报告里有账号，但云端 API 实际登录失败。
4. 小程序源码或缓存仍指向本地 API，开发工具能用，手机或云端测试不能用。
5. 前端静态包已上传，但 API 没重启，后端规则仍是旧版本。
6. 上传后没有跑真实登录 smoke test，导致平台、车公司、司机、旅行社任一入口漏测。
7. 两个小程序共用 AppID 时分别上传会互相覆盖，必须先确认入口策略。

## 固定检查命令

本地执行：

```powershell
python scripts\verify_trial_deploy.py
```

如果只想检查 HTTPS/API，不检查 SSH 服务器环境：

```powershell
python scripts\verify_trial_deploy.py --skip-remote
```

## 必过项目

- `https://api-trial.taxi-airport.jp/api/ping` 返回 `ok=true`。
- `https://admin-trial.taxi-airport.jp/` 的 JS bundle 内含 `https://api-trial.taxi-airport.jp`。
- JS bundle 不再使用 `window.location.origin` 作为云端 API。
- 云端 API 运行环境指向 trial DB：`runtime/trial/wx_dispatch_trial.sqlite3`。
- `admin/admin123` 可以登录平台总控。
- `SKR-08070010000/Test123456` 可以登录车公司管理端。
- `SKR-08070010101/Test123456` 可以登录司机端。
- `AGA2026/Test123456` 可以登录旅行社 portal。
- `080-7101-0101/Test123456` 可以登录旅行社导游账号。

## 发布口径

只有上述全部通过，才能回复“云端已可测”。如果任一失败，先修复并重跑检查，不把链接交给用户反复踩同样问题。
