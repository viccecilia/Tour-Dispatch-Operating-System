# TASK-004：Finance 页面待确认池

## 修改了什么
- React 财务页新增“司机费用待确认池”。
- 显示垫付 / 代收待确认金额、费用列表、司机、订单、路线、类别、金额、状态。
- 支持财务在页面内点击“确认 / 驳回”。

## 涉及文件
- `frontend/src/pages/FinancePage.tsx`
- `frontend/src/services/apiClient.ts`
- `frontend/src/types/api.ts`

## 验证方式
- `npm.cmd run build`
- `npm.cmd run lint`

## 是否完成
- DONE

## 风险
- 需要人工在浏览器中确认 Finance 页面视觉和操作手感。
