# WX-DISPATCH-R038：Driver Voice & Hands-Free Runtime

## 修改了什么
- 小程序司机端新增语音辅助区。
- 支持：
  - 播报下一单
  - 播报下一步
  - 语音确认状态提交
  - Hands-free 大字提示
  - 震动提示
- 不接复杂 AI 语音，不接语音识别。

## 验证结果
- `node --check miniapp/pages/driver/index.js`：通过。
- `python scripts/verify_driver_api.py`：通过。

## 协作验收
- 需要真机确认：
  - 播报按钮是否明显。
  - 微信环境是否支持 `wx.speak`。
  - 不支持 TTS 时，大字弹窗 + 震动是否足够司机使用。
  - “语音确认”是否能减少司机误点。

## 未完成/风险
- 不做复杂 AI 语音。
- 不做语音识别和自然语言命令。
- 如果当前微信环境没有 `wx.speak`，系统会降级为视觉提示，不是真正音频播报。
