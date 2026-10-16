# Phase 1 回滚方案

## 首选：本机功能开关回退

Phase 1 保留了旧司机首页 WXML。需要立即回到旧首页时，在微信开发者工具控制台执行：

```js
wx.setStorageSync('driver_today_workbench_v1', 'legacy')
```

重新进入首页后使用旧司机首页。也可写入 `false`、`0` 或字符串 `false`。恢复新版：

```js
wx.removeStorageSync('driver_today_workbench_v1')
```

功能开关只影响本机首页显示，不修改服务器、订单、任务、日报、费用、通知或文书。

## 代码级回退范围

如后续发布前决定撤销 Phase 1，只需撤销以下三个首页文件的本轮差异：

- `miniapp_yuzu/package_dispatch/pages/home/index.js`
- `miniapp_yuzu/package_dispatch/pages/home/index.wxml`
- `miniapp_yuzu/package_dispatch/pages/home/index.wxss`

不要回退或覆盖用户已有的后端、认证、部署脚本和测试改动。任务、地图、费用、我的页面及底部导航本轮没有修改，无需回退。

## 数据与服务回滚

- 本轮没有 migration、没有 Schema 变化，所以没有数据库回滚步骤。
- 首页没有新增写接口或新表，切换旧首页不会留下平行数据。
- 本轮没有部署或重启 Trial，也没有 Production 操作，所以不存在服务器激活回滚。
- 通知卡“已读”沿用原接口；它只是收件状态，不代表审批。人工验收时不应在真实 Trial 记录上点击。

## 回退验收

1. 旧首页可见且仍读取原 assignments/workbench/profile/notifications。
2. 五个底部入口顺序仍为：首页、任务、地图、费用、我的。
3. 任务页的出库、入库、日报、运行文件、任务确认入口仍在。
4. 费用、地图、个人资料页仍可进入。
5. `git diff -- backend/db` 为空。
