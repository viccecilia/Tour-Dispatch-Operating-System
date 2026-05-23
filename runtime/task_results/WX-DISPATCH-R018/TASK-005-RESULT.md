# TASK-005：司机端位置体验

## 修改了什么
- 司机端报备信息区新增位置上报入口。
- 保留手动位置文字、经纬度输入。
- 定位失败时仍可上报文字位置，避免弱网/权限问题导致完全不可用。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`

## 验证方式
- 需要微信开发者工具/真机人工验证。

## 是否完成
DONE

## 风险
- 位置权限、真机定位精度、微信合法域名配置需要人工检查。
