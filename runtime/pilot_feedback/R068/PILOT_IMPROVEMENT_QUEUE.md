# R068 Pilot Improvement Queue

## Summary

- Total: 2
- P0: 0
- P1: 0
- P2: 2
- P3: 0

## By Status

- new: 2

## By Role

- dispatcher: 1
- driver: 1

## Queue

| ID | Priority | Role | Area | Issue | Expected | Status | Next Action |
|---|---|---|---|---|---|---|---|
| R068-FB-001 | P2 | driver | driver_home | 司机首页需要真机确认下一步按钮是否足够醒目。 | 司机打开首页 3 秒内知道下一步。 | new | 安排司机端真机试运行并截图记录。 |
| R068-FB-002 | P2 | dispatcher | dispatch_mobile | 手机端连续处理 50 单时需要确认滚动和筛选是否顺手。 | 50 单导入、筛选、派车不应占满屏幕后无法操作。 | new | 使用真实订单文本进行批量导入试运行。 |

## Usage

Edit `runtime/pilot_feedback/R068/feedback_items.json`, then run:

```bash
python scripts/generate_pilot_feedback_queue.py
```
