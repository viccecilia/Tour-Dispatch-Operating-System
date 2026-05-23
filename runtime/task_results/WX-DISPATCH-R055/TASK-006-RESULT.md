# TASK-006：我的页面个人中心化

## 修改了什么
- 我的页面改为个人中心结构。
- 增加头像占位、司机基础信息、本月订单/收入/送迎/包车概览。
- 证件提醒、提醒区、工作履历、切换司机分层展示。
- 离线补交任务放入提醒区，不再像输入框式工具。

## 涉及文件
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`
- `docs/DRIVER_UI_GUIDELINES.md`

## 验证方式
- `node --check miniapp/pages/driver/index.js`
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- “本月收入”仍来自既有司机收入 API，未新增工资/结算规则。
