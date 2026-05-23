# TASK-001 司机端首页 Dashboard 重构

## 修改了什么
- 将司机端首页从运营中台指标改为司机每日工作台。
- 增加今日订单、下一单、本月完成、送迎、包车、异常、待报备、待提交费用、车辆/清扫/酒测状态。
- 首页核心改为“下一步”大按钮。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`

## 验证方式
- `node --check miniapp/pages/driver/index.js`
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 小程序真机视觉和微信定位权限仍需人工验收。
