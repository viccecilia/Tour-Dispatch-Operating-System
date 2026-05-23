# TASK-002：首页 Dashboard 收紧

## 修改了什么
- 首页只保留今日/本月司机相关指标：今日订单、下一单、本月送迎、本月包车、本月事故、待提交费用。
- 当前任务卡强化为司机任务卡，突出下一步动作、时间、路线和客人信息。
- 主动作继续固定在底部，避免一页出现多个强按钮。

## 涉及文件
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`

## 验证方式
- `node --check miniapp/pages/driver/index.js`
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 首页视觉已收紧，但最终是否“3 秒能懂”仍需司机真机人工验收。
