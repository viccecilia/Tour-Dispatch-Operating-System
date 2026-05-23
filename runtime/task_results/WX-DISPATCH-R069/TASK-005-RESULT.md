# TASK-005 财务页视觉升级

## 修改了什么
- 财务页改为统计卡 + 费用记录流。
- 展示今日金额、待确认费用、司机垫付、司机代收、订单数、合计金额。
- 清理乱码文案和错误提示。

## 涉及文件
- `miniapp_dispatch/pages/finance/index.js`
- `miniapp_dispatch/pages/finance/index.wxml`
- `miniapp_dispatch/pages/finance/index.wxss`

## 验证方式
- `node --check miniapp_dispatch/pages/finance/index.js`

## 是否完成
DONE

## 风险
- 本轮未改变财务结算规则，只做移动端展示层升级。
