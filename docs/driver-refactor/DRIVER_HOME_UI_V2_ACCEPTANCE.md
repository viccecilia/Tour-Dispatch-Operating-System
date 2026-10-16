# Driver Home UI V2 本地验收记录

日期：2026-10-16（Asia/Tokyo）
分类：IMPLEMENT → LOCAL VERIFY
工作树：`C:\Users\pangv\.codex\worktrees\dispatch-home-port-full\Tour Dispatch Operating System`
基准 HEAD：`176d549c0baa9feb8e671efa05cdacb994108cf1`（detached HEAD）

## 修改范围

- `miniapp_yuzu/package_dispatch/pages/home/index.js`
- `miniapp_yuzu/package_dispatch/pages/home/index.wxml`
- `miniapp_yuzu/package_dispatch/pages/home/index.wxss`
- `scripts/driver_task_ui_v2_local_demo.py`（只用于隔离验收场景）
- `tests/test_driver_home_ui_v2_contract.py`

未修改数据库 Schema、正式订单审批权限、财务金额、文书生成、任务页 UI V2 和五个底部导航。

## 实现结果

1. 司机首页只显示一个紧凑 Hero，合并姓名、编号、车辆、日期、任务数、出入库状态和出入库时间。
2. Hero 状态仅根据 `/api/driver/workflow-events?date=YYYY-MM-DD` 的已提交记录推导：无任务、未出库、运行中、已入库。
3. Hero 状态入口复用既有任务页，并写入既有 `driver_task_yard_focus` 定位参数。
4. 删除司机首页旧的独立日期统计、四数字框、出入库大卡和临时业务大卡。
5. Hero 下固定一排四个入口：运行指示书、运送引受书、司机日报、临时业务。文书仍使用既有下载接口；日报和临时业务仍进入既有页面/API。
6. 临时业务角标仅统计 `draft`、`pending_company_confirmation`、`needs_information` 三类司机待处理记录。
7. 主体直接显示真实今日任务，沿用后端顺序并显示时间、路线、类型、状态和变更提醒；点击进入既有任务页及六项实绩填写。
8. 非司机角色继续走原首页 `<block wx:else>`，未改变其布局与权限。

## 隔离 HTTP 验收

地址：`http://127.0.0.1:18765`
隔离数据库目录：`artifacts/driver-task-ui-v2/`
日期：`2026-10-16`
测试司机：本地 fixture `ui_v2_driver`（不涉及 Trial/Production）

| 场景 | 正式任务 | workflow events | Hero 期望/实际推导 |
| --- | ---: | ---: | --- |
| `no_tasks` | 0 | 0 | 今日无任务 |
| `not_departed` | 3 | 0 | 未出库 |
| `running` | 3 | 2（depart_yard、alcohol_test_out） | 运行中 |
| `returned` | 3 | 4（含 return_yard、alcohol_test_in） | 已入库 |

任务页和 Hero 同时读取同一个日期的 workflow events，因此不存在首页手工伪造状态。

## 自动化结果

- Driver Home UI V2 合约：8/8 通过。
- 首页 Phase 1、任务页 UI V2、M1、Phase 2A、B0、角色/租户隔离组合回归：37/37 通过。
- 全量：224 项；221 通过；3 项为工作树既有 `test_daily_import_dates` 基线错误（测试 SQLite 缺少 `locations` 表），与本次首页文件无关。
- `check-dispatch-miniapp`：通过（17 JS、15 WXML）。
- `node --check package_dispatch/pages/home/index.js`：通过。
- Python 编译检查：通过。
- 目标文件 `git diff --check`：通过。

测试中的 `fault injection` 日志是原事务原子回滚用例主动抛出的异常，该用例通过。

## 微信开发者工具与小屏检查

- 正确项目：`...\dispatch-home-port-full\Tour Dispatch Operating System\miniapp_yuzu`
- AppID：`wx9636a2182beaa078`
- 已打开微信开发者工具项目列表并选中正确项目。
- 当前工具“服务端口”关闭，自动化接口无法点击“打开/编译”；因此本轮尚未取得更新后模拟器截图，不能以静态检查冒充微信开发者工具实机点验。
- 代码已包含 `max-width: 360px` 小屏规则，四入口及任务列均有 `min-width: 0`、省略和窄屏字号处理；实际模拟器截图仍待工具打开后补证。

## 回滚

只需恢复上述三份首页文件，并移除本轮测试/验收辅助文件；不需要回滚数据库、迁移、任务、审批、财务或文书数据。

## 边界确认

- Trial：未访问、未部署、未重启。
- Production：未访问。
- Git：未 commit、未 push、未 reset/clean。
- 微信：未上传、未提审、未发布。
- 业务：未写入真实订单、点呼、日报、临时业务或通知。
