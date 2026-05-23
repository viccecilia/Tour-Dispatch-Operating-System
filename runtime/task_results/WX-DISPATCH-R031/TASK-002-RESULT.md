# TASK-002 下一步大按钮

## 修改了什么
- 根据 execution_status 自动显示唯一主按钮：
  assigned -> 确认订单，confirmed -> 出库，departed -> 到达上车点，arrived -> 开始服务，in_service -> 完成订单，completed -> 归库。
- 提交时禁用按钮，防止重复点击。
- 操作成功后自动刷新任务状态。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`

## 验证方式
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 重复点击防护在 API 层和页面层都有基础保护，但真机弱网场景仍需人工压测。
