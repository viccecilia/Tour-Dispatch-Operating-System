# TASK-003：排行榜与收入排行

## 修改了什么
- 后端按司机收入、完成单、订单数排序输出排名。
- 前端展示司机收入排行条形进度。
- 展示完成数、准时率、客诉数和司机收入。

## 涉及文件
- `backend/services/analytics_service.py`
- `frontend/src/pages/AnalyticsPage.tsx`

## 验证方式
- 实测 Analytics API 第一条司机返回 `rank`、`driver_income`、`completion_rate`、`ontime_rate`、`complaint_rate`。

## 是否完成
DONE

## 风险
- 如果订单未维护 `driver_salary_jpy`，司机收入会显示为 0；后续可和财务结算口径进一步统一。
