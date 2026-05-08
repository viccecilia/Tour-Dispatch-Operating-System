# TASK-002 结果

## 修改了什么

重写 `scripts/demo_seed.py`，固定生成稳定演示数据，不再随机追加。

固定数据包括：

- 40 单今日订单
- 10 单未派车
- 30 单已派车
- 5 单服务中
- 2 单已完成
- 3 单已归库
- 8 台车
- 10 个司机
- 5 个旅行社
- 3 个待确认解析草稿
- 2 个解析失败草稿

## 涉及文件

- `scripts/demo_seed.py`

## 验证方式

运行：

```bash
python scripts/reset_demo_db.py
```

并访问：

```text
GET /api/dashboard/summary
```

稳定结果：

- today_orders: 40
- today_assigned_orders: 30
- today_unassigned_orders: 10
- today_in_service_orders: 5
- today_completed_orders: 2
- today_returned_orders: 3
- today_parsed_drafts: 3
- failed_drafts: 2

## 是否完成

DONE

## 风险

`pending_drafts` 当前 dashboard 统计包含 parsed 和 failed，所以显示为 5；固定数据本身是 3 个待确认草稿加 2 个失败草稿。
