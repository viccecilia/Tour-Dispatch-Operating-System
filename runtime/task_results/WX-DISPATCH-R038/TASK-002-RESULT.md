# TASK-002：状态语音确认

## 修改了什么
- 新增“播报下一步”。
- 新增“语音确认”，先提示下一步动作，再由司机确认提交状态。
- 保留原有下一步大按钮，不改变状态流转接口。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`

## 验证方式
- `node --check miniapp/pages/driver/index.js`
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 本轮不做语音识别，所以不是“口头说确认后自动提交”；仍需要司机点击确认，避免误操作。
