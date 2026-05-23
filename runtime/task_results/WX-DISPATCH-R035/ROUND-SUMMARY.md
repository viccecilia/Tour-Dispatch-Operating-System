# WX-DISPATCH-R035：Driver Offline Runtime

## 修改了什么
- 建立小程序司机端离线队列。
- 报备和位置上报失败时不丢数据，进入本地待补发队列。
- 网络恢复后自动补发，也支持手动补发。
- 页面显示在线/离线、弱网提示、待补发数量和补发按钮。
- 清理司机页文案，恢复为中文可读状态。

## 验证结果
- `node --check miniapp/pages/driver/index.js`：通过。
- `node --check miniapp/utils/offlineQueue.js`：通过。
- `python scripts/verify_driver_api.py`：通过。

## 协作验收
- 需要真机或微信开发者工具人工模拟断网：
  1. 打开司机页。
  2. 断网后点击下一步报备。
  3. 确认页面显示待补发。
  4. 恢复网络。
  5. 确认自动补发或点击补发后状态同步。

## 未完成/风险
- 本轮不做复杂同步引擎，不处理多设备冲突。
- 离线队列依赖微信本地 storage。
- 真实弱网表现需手机验收。
