# TASK-004 Finance UX 修复

## 修改了什么
- Finance 页面顶部增加财务试运营核对提示：
  - 日期/司机筛选
  - 垫付/代收待确认
  - 确认费用影响结算
  - 导出前检查状态

## 涉及文件
- `frontend/src/pages/FinancePage.tsx`
- `frontend/src/components/PilotFeedbackNote.tsx`

## 验证方式
- `npm.cmd run build`
- 浏览器检查 `#finance` 页面试运营提示可见。

## 是否完成
DONE

## 风险
- 未新增财务业务字段，符合“不新增大功能”约束。
