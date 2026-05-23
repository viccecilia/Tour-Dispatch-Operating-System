# TASK-002 底部 Tab 与顶部状态卡

## 修改了什么
- 新增底部五 Tab：`首页`、`出入库`、`任务地图`、`费用`、`我的`。
- 顶部司机状态卡固定保留，显示司机姓名、日期时间、司机 ID、在线状态、出库状态。

## 涉及文件
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`
- `miniapp/pages/driver/index.js`

## 验证方式
- `node --check miniapp/pages/driver/index.js`

## 是否完成
DONE

## 风险
- 由于小程序 WXML 需要微信开发者工具编译确认，本轮只能完成代码侧结构与 JS 语法验证。
