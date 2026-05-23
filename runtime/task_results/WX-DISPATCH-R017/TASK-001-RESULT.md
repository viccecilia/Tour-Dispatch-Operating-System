# TASK-001：司机端大按钮与当前任务突出

## 修改了什么
- 重做 `miniapp/pages/driver/` 为手机优先布局。
- 当前任务改为顶部大卡片展示。
- 下一步动作改为全宽大按钮。
- 订单时间、路线、车辆、客人、备注集中显示。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`

## 验证方式
- 人工真机/微信开发者工具预览。
- `python scripts/verify_driver_api.py` 验证后端状态流。

## 是否完成
DONE

## 风险
- 小程序真机视觉仍需人工确认，不在命令行自动验证范围内。
