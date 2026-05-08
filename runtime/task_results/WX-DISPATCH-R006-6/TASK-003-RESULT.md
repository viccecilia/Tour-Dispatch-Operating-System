# TASK-003 结果

## 修改了什么

修复并明确启动配置和小程序 API 地址配置。

后端：

- `backend/main.py` 已支持 `WX_DISPATCH_PORT`。
- 默认端口仍为 `8000`。

小程序：

- `miniapp/utils/api.js` 增加集中配置 `API_CONFIG.baseUrl`。
- 增加 `setBaseUrl()` 和 `getBaseUrl()`。
- 注释说明真机预览要改成电脑局域网 IP。

文档：

- 新增 `docs/STARTUP_GUIDE.md`。
- 重写 `wx_dispatch_platform/README.md`。

## 涉及文件

- `miniapp/utils/api.js`
- `docs/STARTUP_GUIDE.md`
- `wx_dispatch_platform/README.md`

## 验证方式

本机 8000 当前被其他服务占用，本轮按文档备用端口启动：

```bash
$env:WX_DISPATCH_PORT='18765'
python backend/main.py
```

验证：

```text
GET http://127.0.0.1:18765/api/ping
```

返回：

```json
{"ok": true, "message": "pong"}
```

## 是否完成

DONE

## 风险

真机预览时 `127.0.0.1` 指向手机自己，不是电脑；必须把 `miniapp/utils/api.js` 改成电脑局域网 IP，并在微信开发者工具勾选“不校验合法域名”。
