# TASK-003：离线提示与司机体验

## 修改了什么
- 离线时展示明确提示：操作会先保存到本机。
- 弱网时提示提交失败会进入待补发队列。
- 顶部显示待补发数量。
- 下一步按钮、位置上报、实时位置同步失败时不白屏。

## 涉及文件
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`
- `miniapp/pages/driver/index.js`

## 验证方式
- `node --check miniapp/pages/driver/index.js`

## 是否完成
DONE

## 风险
- 弱网体验需要人工模拟断网、2G/3G 或请求失败场景确认。
