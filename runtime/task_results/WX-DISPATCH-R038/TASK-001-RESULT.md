# TASK-001：下一单语音播报

## 修改了什么
- 司机页新增语音辅助区。
- 支持“播报下一单”，内容包含日期时间、路线、客人、车辆和下一步动作。
- 进入/切换当前任务时可自动生成当前任务播报文本。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`

## 验证方式
- `node --check miniapp/pages/driver/index.js`

## 是否完成
DONE

## 风险
- 微信小程序没有稳定通用的内置 TTS API，本轮优先尝试 `wx.speak`，不可用则降级为大字弹窗提示和震动。
