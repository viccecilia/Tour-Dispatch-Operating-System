# TASK-002：运营分析页面骨架补齐

## 修改了什么
- 经营分析接口失败时仍展示标题、筛选、KPI 区、司机绩效、收入排行、订单趋势、旅行社收入、车辆利用率。
- KPI loading 使用 skeleton。
- 无数据模块使用 EmptyPanel，接口失败显示 ErrorPanel。

## 涉及文件
- `frontend/src/pages/AnalyticsPage.tsx`

## 验证方式
- `npm run build`
- `npm run lint`
- 浏览器检查 `http://127.0.0.1:5173/#analytics`

## 是否完成
DONE

## 风险
- 图表仍是轻量占位/条形图，未引入复杂图表库。
