# TASK-003：Hands-free 提示

## 修改了什么
- 新增语音辅助开关。
- 播报时同步展示最近播报文本。
- 如果没有 TTS 能力，使用震动 + 大字弹窗，司机不用阅读复杂表格也能获得下一步信息。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`

## 验证方式
- `node --check miniapp/pages/driver/index.js`

## 是否完成
DONE

## 风险
- Hands-free 体验必须在真机环境确认，开发者工具无法完全模拟车内使用场景。
