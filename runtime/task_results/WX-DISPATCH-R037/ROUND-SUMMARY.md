# WX-DISPATCH-R037：Driver Performance & Rating

## 修改了什么
- 建立第一版司机绩效系统。
- Analytics API 返回司机完成率、准时率、客诉率、收入排行和司机 KPI。
- React Analytics 页面升级为中文司机绩效与经营 BI 看板。
- 增加 KPI 口径说明，避免被误解为复杂 HR 绩效。

## 验证结果
- `python -m compileall backend scripts`：通过。
- `python scripts/health_check.py`：通过。
- `cd frontend && npm.cmd run build`：通过。
- `cd frontend && npm.cmd run lint`：通过。
- API 实测通过：
  - `driver_count`
  - `avg_driver_completion_rate`
  - `avg_driver_ontime_rate`
  - `rank`
  - `driver_income`
  - `completion_rate`
  - `ontime_rate`
  - `complaint_rate`

## 协作验收
- 需要人工确认：
  - 完成率是否符合运营理解。
  - 准时率 15 分钟宽限是否合理。
  - 客诉率是否只统计 complaint 异常。
  - 收入排行是否使用司机工资字段作为第一版口径。

## 未完成/风险
- 不做复杂 HR 绩效。
- 司机收入依赖订单 `driver_salary_jpy` 字段。
- 准时率需要真实报备数据支撑；demo 数据下仅用于功能验证。
