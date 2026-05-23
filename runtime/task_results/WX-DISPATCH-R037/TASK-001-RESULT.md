# TASK-001：司机 KPI 后端统计

## 修改了什么
- 扩展 Analytics 后端司机绩效统计。
- 增加司机完成率、准时率、客诉率、收入排行字段。
- 增加总体司机数量、平均完成率、平均准时率。

## 涉及文件
- `backend/services/analytics_service.py`

## 验证方式
- `python -m compileall backend scripts`
- 实测 `GET /api/analytics/summary` 返回 `driver_count`、`avg_driver_ontime_rate`、`driver_income`、`complaint_rate` 等字段。

## 是否完成
DONE

## 风险
- 准时率当前按“到达上车点或开始服务报备时间 <= 计划开始时间 + 15 分钟”计算，需要试运行后校准。
