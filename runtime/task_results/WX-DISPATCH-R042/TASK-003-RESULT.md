# TASK-003 现有司机模块迁移

## 修改了什么
- 首页保留今日订单、待确认订单、当前订单、下一步大按钮。
- 出入库页迁移车灯、刹车、车身、驾照、乘务员证、酒测、睡眠确认。
- 任务地图页迁移定位上报、导航、照片节点。
- 费用页迁移垫付/代收费用提交入口。
- 我的页迁移司机切换、提醒中心、工作履历和离线补交入口。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`

## 验证方式
- `python scripts/verify_driver_api.py`
- `node --check miniapp/pages/driver/index.js`

## 是否完成
DONE

## 风险
- 费用与照片入口仍沿用已有后端接口，本轮未新增复杂费用逻辑或云存储能力。
