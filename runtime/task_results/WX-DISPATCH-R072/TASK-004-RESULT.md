# TASK-004 RESULT

## 修改了什么
- 司机小程序和调度小程序 API 地址改为集中配置。
- 支持本地默认地址、storage 覆盖地址和云端 HTTPS 地址切换。
- 移除硬编码的 `127.0.0.1` 与 `192.168.x.x` 作为唯一地址。

## 涉及文件
- `miniapp/utils/api.js`
- `miniapp_dispatch/utils/api.js`
- `docs/INTERNAL_TEST_DEPLOY_GUIDE.md`

## 验证方式
- `node --check miniapp/pages/driver/index.js`
- `node --check miniapp_dispatch/pages/index/index.js`
- `node --check miniapp_dispatch/pages/dispatch/index.js`

## 是否完成
DONE

## 风险
- 微信体验版必须配置 HTTPS 合法域名，真机不能使用 localhost。
