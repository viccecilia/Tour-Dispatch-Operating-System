# TASK-002 Weak Network & Startup Optimization

## 修改了什么
- 增加 60 秒自动同步任务状态。
- 增加请求节流，避免 `onLoad` / `onShow` / 网络恢复时重复打 API。
- 网络恢复后继续补发离线队列，并强制刷新一次任务状态。
- 补发异常时会释放 retrying 状态，避免界面长期停在补发中。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`

## 验证方式
- `node --check miniapp/pages/driver/index.js`
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 弱网缓存逻辑已保留，但真实弱网抖动、后台切前台、长时间运行仍需要真机连续测试。
