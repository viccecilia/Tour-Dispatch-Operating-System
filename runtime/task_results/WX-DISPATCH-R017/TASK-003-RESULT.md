# TASK-003：一键下一步与防误触

## 修改了什么
- 根据 execution_status 自动显示下一步动作。
- 点击大按钮后弹出二次确认。
- 提交中禁用按钮，防止重复提交。
- 离线时阻止提交并提示。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`

## 验证方式
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 小程序端未接正式司机登录，仍通过 driver_id 识别司机。
