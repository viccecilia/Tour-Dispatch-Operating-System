# 启动指南

## 1. 初始化并重置演示数据

在项目根目录运行：

```bash
python scripts/reset_demo_db.py
```

这个命令会删除旧的本地演示库，重新创建表结构，并写入固定 demo 数据。重复运行不会无限累加订单。

## 2. 启动后端

默认端口是 `8000`：

```bash
python backend/main.py
```

启动后访问：

- API 心跳：`http://127.0.0.1:8000/api/ping`
- 调度台：`http://127.0.0.1:8000/dashboard`

如果 `8000` 被占用，可以切换端口：

```bash
$env:WX_DISPATCH_PORT='18765'
python backend/main.py
```

对应访问：

- `http://127.0.0.1:18765/dashboard`

## 3. 小程序 API 地址

小程序 API 地址集中在：

```text
miniapp/utils/api.js
```

默认：

```javascript
baseUrl: 'http://127.0.0.1:8000'
```

微信开发者工具本机预览可以使用 `127.0.0.1`。真机预览时，需要改成电脑在同一 Wi-Fi 下的局域网 IP，例如：

```javascript
baseUrl: 'http://192.168.1.23:8000'
```

如果后端使用 `18765`，小程序也要同步改为：

```javascript
baseUrl: 'http://192.168.1.23:18765'
```

## 4. 微信开发者工具设置

开发阶段需要在微信开发者工具中勾选：

```text
不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书
```

否则本地 HTTP API 请求可能被拦截。

## 5. 常见问题

### dashboard 没有数据

先运行：

```bash
python scripts/reset_demo_db.py
```

### API 请求失败

检查：

- 后端是否启动。
- 小程序 `miniapp/utils/api.js` 的 `baseUrl` 是否和后端端口一致。
- 真机和电脑是否在同一 Wi-Fi。
- Windows 防火墙是否允许 Python 进程访问局域网。

### 端口被占用

切换端口：

```bash
$env:WX_DISPATCH_PORT='18765'
python backend/main.py
```
