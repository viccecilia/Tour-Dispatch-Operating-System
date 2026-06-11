# 柚子调度统一小程序最终迁移报告

日期：2026-06-11

## 迁移范围

- 新统一小程序目录：`miniapp_yuzu`
- 车公司端业务迁入：入口首页、派车、订单大厅、地图、财务、司机任务、费用、我的、订单导入、搜索、司机车辆信息、日历
- 旅行社端业务迁入：入口首页、入单、订单大厅、订单跟踪、日历、设置/我的
- 原目录保留：`miniapp_dispatch`、`miniapp_agency` 未覆盖

## 核心适配

- `miniapp_yuzu/app.json` 已注册统一入口、登录页、车公司分包、旅行社分包
- 统一登录成功后写入：
  - `yuzu_session`
  - `dispatcher_session:<api_base_url>`
  - `tourflow_agency_session`
- 车公司/旅行社页面继续使用包内 `utils/api.js`，避免互相污染
- 原 `/pages/...` 页面跳转已迁移到：
  - `/package_dispatch/pages/...`
  - `/package_agency/pages/...`
- 原车公司自定义 tabbar 已迁入 `miniapp_yuzu/custom-tab-bar`

## 本地验证

- JS 语法检查：通过
- JSON 解析检查：通过
- `app.json` 注册页面文件存在检查：通过
- 组件引用检查：通过
- `getSystemInfoSync` / `wx.switchTab` / 阶段二占位文案残留扫描：通过

## 下一步测试

1. 微信开发者工具打开 `miniapp_yuzu`
2. 测试统一入口：
   - 选择旅行社
   - 选择车公司
3. 测试登录：
   - 旅行社 portal 登录
   - 旅行社手机号角色登录
   - 车公司管理/调度/运行管理/司机登录
4. 跑订单主链路：
   - 旅行社入单
   - 发布到订单大厅
   - 车公司竞拍/一口价接单
   - 车公司派车
   - 司机确认、点呼出库、执行、入库
   - 财务结算

## 注意

本轮只完成本地统一小程序迁移，未上传微信小程序后台，未部署云端，未推送 GitHub。
