# TASK-002 首页 Dashboard 重构

## 修改了什么
- 首页改为物流移动端 Dashboard 风格。
- 强化未派车、今日订单、待确认、在线司机、异常订单、通知等运营入口。
- 登录后页面不再像后台统计页，改为更清爽的卡片结构。

## 涉及文件
- `miniapp_dispatch/pages/index/index.wxml`
- `miniapp_dispatch/pages/index/index.wxss`

## 验证方式
- `node --check miniapp_dispatch/pages/index/index.js`

## 是否完成
DONE

## 风险
- KPI 数据仍依赖现有后端接口；接口失败时需要继续做更高级离线状态。
