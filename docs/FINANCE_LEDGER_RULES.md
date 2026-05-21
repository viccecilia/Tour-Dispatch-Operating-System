# 财务订单台账规则

## 定位

财务模块不是独立统计页，而是订单大表的财务视角。数据来源为：

- `orders`
- `assignments`
- `drivers`
- `vehicles`
- `agencies`

司机端不返回订单价格字段。价格、司机垫付、代收款、旅行社结算和司机结算只在财务端维护。

## 财务主表字段

主表优先显示：

- 日期
- 订单号
- 旅行社
- 司机
- 订单类型
- 执行状态
- 订单价格
- 司机垫付
- 司机代收
- 司机结算状态
- 旅行社结算状态

行程信息默认折叠，展开后显示：

- 起点
- 终点
- 开始/结束时间
- 车辆
- 客人信息
- 备注
- 费用备注

## 执行状态映射

原始 `execution_status` 保留，同时财务页显示分组：

- 未执行：`assigned`、`confirmed`
- 执行中：`departed`、`arrived`、`in_service`
- 已完成：`completed`、`returned`

## 财务状态

旅行社结算状态：

- `pending`：未结算
- `settled`：已结算
- `paid`：已收款
- `unsettled`：未结账

司机结算状态：

- `pending`：未结算
- `settled`：已结算
- `paid`：已支付
- `unsettled`：未结账

## 金额字段

- `price`：订单价格
- `driver_advance_amount`：司机垫付金额
- `driver_collect_amount`：司机代收金额
- `driver_settlement_amount`：应与司机结算金额
- `driver_settlement_note`：司机结算备注

本轮暂由财务端维护司机垫付/代收。后续可以从司机端报备扩展，但不能绕过财务确认。

## 审计

财务端修改订单价格、司机垫付、司机代收、司机结算状态、旅行社结算状态时，写入 `audit_logs`：

- `action = finance_update`
- `entity_type = order`
- `entity_id = order.id`

## 司机端价格隐藏

司机端 API 不返回 `price` 字段。司机可以看到任务、路线、客人信息和执行状态，但不能看到订单价格。
