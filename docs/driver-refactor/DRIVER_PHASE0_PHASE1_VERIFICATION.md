# Driver Phase 0 / Phase 1 验证记录

## 1. 基准

- 工作树：`C:\Users\pangv\.codex\worktrees\dispatch-home-port-full\Tour Dispatch Operating System`
- HEAD：`176d549c0baa9feb8e671efa05cdacb994108cf1`
- Git 状态：detached HEAD；本轮未建分支、未 commit、未 push。
- 实施范围：Phase 0 只读审计 + Phase 1 司机首页外壳。
- 微信开发者工具实际项目：上述工作树的 `miniapp_yuzu`。
- AppID：`wx9636a2182beaa078`。
- 微信开发者工具：`2.02.2609231 RC`，基础库 `3.16.1`。
- `DAITORA_DRIVER_HOME_DEMO_V3_4.html` 仅用于首页信息层级参考，没有作为平行离线应用接入。
- `DAITORA_DAILY_REPORT_ONE_PAGE_V2.pdf` 已做页面结构参考；正式电子日报属于 Phase 2，本轮未改 PDF/Renderer 或日报数据结构。

## 2. Phase 1 实际实现

- 新司机首页按当日工作台排列：司机/车辆/日期/当前状态、今日任务统计、未读变更、两种运行文书和日报快捷入口、出入库摘要、今日订单原位只读展开、日报状态。
- 新首页只组合既有 assignments、workbench、profile、notifications、daily-report、run-documents 响应。
- 所有业务写操作继续进入原任务页或费用页；首页不保存第二份业务记录。
- 司机角色不再请求本来就无权访问的 dispatch dashboard，避免把预期 403 当作首页故障；非司机首页路径未改变。
- 本机 feature flag `driver_today_workbench_v1` 可即时回到保留的旧首页。

## 3. 真实接口和角色隔离证据

隔离测试启动真实本地 HTTP 服务和临时 SQLite，通过 Bearer 会话调用路由，而非只测试函数：

- 司机 A 请求 `GET /api/driver/assignments?driver_id=<司机B>`，返回仍仅包含司机 A 自己的 active、published、未删除任务。
- 同样伪造 `driver_id=<司机B>` 请求日报、费用、运行文书和通知接口，均只返回司机 A 自己的记录；司机 B 的标记记录未泄露。
- admin 请求 `GET /api/driver/workbench`，返回 403；`/api/driver/*` 不因管理员权限而旁路司机身份。
- 司机 A 向 `POST /api/driver/workflow-event` 伪造司机 B 的 `driver_id`，路由以会话 `profile_id` 覆盖请求值，写入仍归属司机 A。

代码链同时确认 tenant 上下文来自已认证用户；assignment/order/run document/daily report/expense/notification 的查询和写入继续经过既有本人归属校验。

## 4. 微信开发者工具实际点击

使用当前已登录的 Trial 司机会话做只读显示和导航核对；未点击任何提交、确认、上传、出库、入库或通知已读操作：

- 新首页成功编译并显示当前司机 `平山由奈 YuzuDriver / D10422`，日期、状态、统计、快捷入口、出入库/日报摘要和五项底部导航可见。
- 原任务页可进入，点呼出库、日历、日报草稿/提交、当日任务、点呼入库等既有区域仍在。
- 原费用页可进入，原费用类型、金额、备注、凭证和提交区域仍在。
- 原地图页可进入，当前任务和待执行任务区域仍在。
- 原“我的”页可进入并加载当前司机资料；未编辑资料、未退出登录。
- 最后已返回新司机首页。

证据截图：`artifacts/driver-refactor/driver-home-phase1-devtools.jpg`。

## 5. 自动化结果

- `node --check miniapp_yuzu/package_dispatch/pages/home/index.js`：通过。
- `node miniapp_yuzu/package_dispatch/scripts/check-dispatch-miniapp.js`：通过，`16 js, 14 wxml`。
- `python -m unittest` 相关回归：司机首页契约、真实 HTTP 角色隔离、鉴权账号、运行文书、日报和现有小程序契约共 76 项通过。
- 其中真实 HTTP 角色隔离 3 项覆盖任务、写入身份覆盖、角色拒绝、日报、费用、运行文书和通知。
- `git diff --check`：通过。

## 6. 明确未执行

- 未执行真机调试；开发者工具模拟器不能替代真机验收。
- 未在 Trial 提交出库、入库、日报、费用、任务确认或通知已读；只读导航不能替代真实业务写入验收。
- 当前司机当日无已发布任务，因此未实际打开当前日运行 PDF，也未验证有任务时的订单排序和状态颜色。
- 未执行弱网/离线、键盘遮挡、不同机型、长列表滚动和附件上传实机验收。
- 未部署或重启 Trial；未访问 Production；未 commit/push；未上传微信版本；未发布文书或发送真实通知。

## 7. 数据库与兼容性结论

- Phase 1 没有新增 API、表、列、索引或 migration。
- 任务页、费用页、地图页、个人资料页和底部导航源文件没有修改。
- 旧首页仍保留在 WXML 中并可由本机 feature flag 回退。
- 下一阶段若实施结构化实绩，必须依照 `DRIVER_PHASE2_MIGRATION_DRAFT.md` 单独评审和授权。
