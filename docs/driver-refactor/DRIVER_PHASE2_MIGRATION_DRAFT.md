# Phase 2 迁移草案（未执行）

## 状态与边界

- 本文件只记录下一阶段方案，不是 migration 文件。
- Phase 0/1 未修改数据库 Schema，也没有执行或登记 migration。
- Phase 2 开始前必须先比较 `schema_migrations`、实际列/索引/约束和当前服务代码；禁止重跑历史 migration。
- 所有扩展必须追加式、可回滚，并先在 Trial 数据库的一致性隔离副本演练；不得以本地样例库覆盖 Trial。

## 复用现有正式数据链

| 业务语义 | 既有落点 | Phase 2 原则 |
|---|---|---|
| 公司发布的计划节点 | `dispatch_route_nodes` | 只读计划，不被司机实绩改写 |
| 司机实际到离、地点、里程 | `dispatch_route_node_actuals` | 优先复用，不另建 `driver_trip_points` |
| 出入库、酒测、点呼 | `driver_workflow_events` | 继续同一事件链和附件链 |
| 日常点检 | `driver_daily_inspections` | 继续同表，不复制到日报私有表 |
| 费用 | `driver_expense_reports` | 继续财务共享记录 |
| 日报头、草稿、提交状态 | `driver_daily_reports` | 继续同一日报，不建立第二套日报 |
| 文书收件/确认 | `dispatch_document_receipts`、`dispatch_document_events` | 收件不等于修改计划或审核通过 |

稳定关联键必须是 `tenant_id + driver_id + assignment_id + order_id + run_group_id + route_node_id + business_date` 中适用的组合；不得使用数组下标、显示顺序、司机姓名或车牌尾号代替数据库 ID。

## 建议的兼容 API（全部为追加，旧 API 保留）

- `GET /api/driver/day-workbench?date=YYYY-MM-DD`
- `POST /api/driver/route-node-actual`
- `POST /api/driver/route-node-actual/batch`
- `GET /api/driver/daily-report/preview?date=YYYY-MM-DD`
- `POST /api/driver/daily-report/finalize`
- `GET /api/driver/daily-report/file?date=YYYY-MM-DD`
- `POST /api/driver/document-receipt`
- `POST /api/driver/change-request`

每个新增写接口必须同时校验：

1. 鉴权用户是 `driver`。
2. 请求中的司机身份强制取登录会话的 `profile_id`。
3. tenant 一致。
4. assignment、order、run_group、route_node 属于本人可见且已发布的数据链。
5. `client_request_id` 幂等，网络重试不重复建记录。
6. `expected_revision` 或 source hash 防止并发静默覆盖。
7. 实际发生时间与上传时间分开保存，并写入既有审计链。

## 可能的追加字段门禁

先证明 `dispatch_route_node_actuals` 的既有字段不足，才能提出独立的新 migration。允许的最小扩展方向仅包括：

- 幂等请求号和唯一约束；
- 计划源 revision/hash；
- 本地记录时间、实际发生时间、服务器接收时间；
- 必要的审计来源、设备/离线同步状态；
- 不足以承载多附件时的追加关联表。

不得改变旧字段语义，不得删除旧列，不得回填猜测值，不得在应用启动时反复覆盖已有值。

## 计划与实绩分离

- 司机记录晚到、实际地点或里程，只写实绩链。
- 司机需要改变正式计划时提交变更申请；司机不能直接改 `orders`、计划节点或双文书。
- 调度/运管批准后才通过现有订单更新服务生成新计划 revision，并将当前双文书标记 stale、生成新版本、通知司机。
- 已保存实绩按稳定 `route_node_id` 继续关联；旧 PDF、旧计划和旧实绩均不得覆盖。
- `driver_order_change_requests` 属于后续明确审批流程；若实施，必须是单独评审的追加 migration，不混入 Phase 2 实绩核心迁移。

## 演练与回滚要求

1. 制作一致性数据库副本并记录 SHA-256、表数量和完整性检查。
2. 在副本执行 migration，核对列、索引、唯一约束和旧记录指纹。
3. 重复执行项目 migration 机制，必须安全跳过已登记项且无重复 DDL。
4. 用两个 tenant、两个 driver 验证跨司机/跨 tenant 拒绝。
5. 用相同 `client_request_id` 重放，记录数不得增加。
6. 用过期 revision 提交，必须返回冲突而非覆盖。
7. 回滚仅撤销新增代码入口；如 migration 已产生新业务写入，不允许用旧数据库备份整体覆盖，需执行事先评审的前向兼容回滚。
