# HANDOFF - Yuzu/Daitora Dispatch Checkpoint

## 当前状态
- 检查时间：2026-07-21 JST
- 分支：codex/company-lite-port-snapshot
- 当前 HEAD：697d1f0cf6e9854e9407d762b17d75f833d3c035
- 本检查点未提交：frontend lint 未通过，按用户要求仅在测试通过时提交。
- 未 push。

## 本次任务最终目标
- 仅处理 `miniapp_yuzu/package_dispatch` 小程序车公司端，以及为其必要联动的 Daitora 车辆/司机资料 API/后台数据。
- 管理、调度、运管、司机端围绕 Daitora 真实车辆/人员资料、派单、任务日历、点呼出入库、资料到期提醒形成一套一致数据源。
- 后台车辆/司机页面保留现有后台设计系统，迁入参考页的字段、统计、筛选、下载、状态维护能力。

## 已完成内容
- 小程序 `package_dispatch` 多轮修复：底部 tab、派车/日配入口、首页 dashboard 卡片、通知铃铛、车辆/人员资料入口与提醒区。
- 日配/派车解析预览做成紧凑列表，支持司机分组、车牌简码、司机/车辆/订单统计。
- 司机端任务页增加周历/月历、点呼出库/入库入口、酒精测试/日报/照片上传入口雏形。
- 资料总览页读取 Daitora 车辆、司机、PDF资料、车检/点检/体检提醒，并支持车辆/人员视图切换、事务所/状态筛选雏形。
- 后台/接口方向尝试同步 Daitora 管理号、运管号与真实资源数据，初步区分 `admin`、`operations_manager` 等角色。
- “司机监控”改称“任务监控”的方向已确认/部分调整。
- 已加入或调整字段映射：事务所、状态、车牌尾号、HiAce/Nissan/Alphard 分类、健康体检日期等。

## 尚未完成内容
- frontend lint 未通过，本阶段未提交。
- `08046447554` 管理号与 `08046447555` 运管号仍疑似读取不同视图/租户资料，需要统一 Daitora 数据源。
- 后台车辆/司机页面功能与参考资料页仍有差距：统计、筛选、字段、编辑/保存、下载、资料历史、离职/废车状态还未完全对齐。
- 小程序资料页的上传/更新动作仍需和服务器 API 完整打通。
- 日历页面曾出现加载失败，需要继续定位。
- `/api/dispatch-mobile/assignments` 返回 500，需要后端排查。
- `/api/dispatch-mobile/resource-library/driver-status` 等状态更新接口曾返回 404/not_found，需要补齐或改正确路径。
- 微信开发者工具仍有 `clickCheckTask` 内部错误、重复 `wx:key` 警告，后续需要区分真实业务错误和工具噪声。

## 修改过的文件
- 工作区非常大：tracked changed 约 162，untracked 约 2964。下一窗口必须先运行 `git status --short` 和 `git diff --name-only` 精确核对后再 stage。
- 重点涉及：
  - `miniapp_yuzu/package_dispatch/pages/home/*`
  - `miniapp_yuzu/package_dispatch/pages/info/*`
  - `miniapp_yuzu/package_dispatch/pages/calendar/*`
  - `miniapp_yuzu/package_dispatch/pages/dispatch/*`
  - `miniapp_yuzu/package_dispatch/pages/task/*`
  - `miniapp_yuzu/package_dispatch/utils/api.js`
  - `miniapp_yuzu/utils/port-nav.js`
  - `miniapp_yuzu/app.json`
  - `miniapp_yuzu/app.wxss`
  - `miniapp_yuzu/custom-tab-bar/*`
  - 后端 API / routes / services / db 相关文件
  - 前端后台车辆/司机页面、服务层、组件相关文件
  - `HANDOFF.md`

## 当前数据源和 API
- 本地 API：`http://127.0.0.1:18765`
- Trial API：`https://api-trial.taxi-airport.jp`
- 后台：`https://admin-trial.taxi-airport.jp`
- 车辆资料库：`https://admin-trial.taxi-airport.jp/vehicle-docs/index.html?v=20260716165152`
- 司机信息表：`https://admin-trial.taxi-airport.jp/vehicle-docs/%E5%8F%B8%E6%9C%BA%E4%BF%A1%E6%81%AF%E8%A1%A8.html?v=20260717173353`
- Activity window：`https://admin-trial.taxi-airport.jp/activity-window/`
- 小程序车公司端：`miniapp_yuzu/package_dispatch`

## 已确认字段映射
- Daitora 管理号 `08046447554` 和运管号 `08046447555` 应读同一套 Daitora 车辆/人员资料。
- `本社` / `总社` / 非京都默认大阪；`京都営業所` 显示为京都。
- 车牌尾号不足 4 位不补零：`719`、`710` 原样显示。
- 调度可用车辆分类：HiAce + Nissan 归入 10 座/HiAce；Alphard 单独统计。
- 车辆维护节奏：12个月车检 -> 3个月点检 -> 3个月点检 -> 3个月点检 -> 12个月车检。
- 到期提醒窗口当前要求改为 30 天；已过期继续显示。
- `自動車檢查証記録事項` 的最新日期是最新车检日期。
- 司机健康体检显示应使用 `健康診断日`，不要把 `免许有效期限` 当作体检日期；剩余天数按体检有效期计算。
- 人员状态：在职 / 休假 / 离职。
- 车辆状态：运行 / 维修 / 废车。
- 离职人员不删除资料，真正删除需二次确认，删除优先在离职页处理。

## 测试结果
- `node miniapp_yuzu\package_dispatch\scripts\check-dispatch-miniapp.js`：通过。
- WXML 非法标签扫描：无匹配，通过。
- 关键 JS `node --check`：通过。
- 后端 Python AST parse：48 个文件通过。
- frontend build：通过。
- frontend test：无 test script。
- frontend lint：失败，因此未提交。详细日志见 `%TEMP%\codex_frontend_lint.log`。

## 已知问题
- 当前工作区包含大量未跟踪文件，不能盲目 `git add .`。
- 部分服务器 API 500/404 是真实阻塞，不应仅靠前端兜底掩盖。
- 管理端/运管端资料数据口径不一致。
- 资料页和后台参考页功能结构仍未完全合并。
- 部分小程序页面可能仍有重复 `wx:key` 警告。
- 如果上传小程序后仍旧逻辑不变，需要确认开发者工具缓存、上传版本、服务器 API 与小程序 baseUrl。

## 下一步准确执行顺序
1. 停止新 UI 需求，先修 lint。
2. 运行 `git status --short`、`git diff --name-only`，确认只处理本任务文件。
3. 打开 `%TEMP%\codex_frontend_lint.log` 或重跑 `npm.cmd --prefix frontend run lint`，逐条修复 lint。
4. 启动本地 API，分别验证 `08046447554 / 447554`、`08046447555 / 447554` 登录。
5. 统一 Daitora tenant/resource 数据源，确保管理号和运管号读取同一套车辆/人员/PDF/提醒数据。
6. 修 `/api/dispatch-mobile/assignments` 500。
7. 补齐或更正 resource-library 状态/上传接口，尤其 `driver-status`、vehicle status、体检/点检/车检上传。
8. 按参考资料页完善后台车辆/司机页面的信息结构和功能，但保留现有后台视觉系统。
9. 回到小程序资料总览页，确认车辆/人员、状态、事务所、提醒、下载、上传全部读同一 API。
10. 重跑 miniapp check、WXML scan、node --check、backend AST、frontend lint/build。
11. 全部通过后，只 stage 意图内文件，本地 commit，不 push。

## 当前 commit SHA
`697d1f0cf6e9854e9407d762b17d75f833d3c035`
# Checkpoint 2026-07-24

- Daitora test runtime orders were cleared after verification: cloud tenant 8204 had 3 test orders, 1 active assignment, and 10 parser drafts; the assignment was cancelled, orders were soft-deleted, and drafts were discarded.
- Local test runtime data was backed up to `runtime/backups/pre_reset_orders_20260724_105425_wx_dispatch.sqlite3` and cleared with `scripts/reset_test_orders.py`.
- Validation passed: frontend ESLint (warnings only), frontend production build, dispatch miniapp package check, WXML scan, key JavaScript `node --check`, backend Python AST, and `git diff --check`.
- This checkpoint preserves vehicle, driver, account, company, PDF, and resource-library data.
