# TASK-002：网络恢复重试

## 修改了什么
- 监听网络状态变化。
- 网络从离线恢复后自动补发当前司机的待提交记录。
- 页面提供“立即补发 / 重试待补发”按钮。
- 补发成功后从队列移除，失败时保留并记录错误。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`

## 验证方式
- `node --check miniapp/pages/driver/index.js`

## 是否完成
DONE

## 风险
- 真机网络状态回调行为需要在微信开发者工具和手机上实测。
