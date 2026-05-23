# TASK-002 Dispatch UX 修复

## 修改了什么
- Dispatch 页面顶部增加试运营检查提示：
  - 先选订单再选司机/车辆
  - 冲突提示必须处理
  - 派车后检查已分配池
  - 司机端会收到任务

## 涉及文件
- `frontend/src/pages/DispatchPage.tsx`
- `frontend/src/components/PilotFeedbackNote.tsx`

## 验证方式
- `npm.cmd run build`
- 浏览器检查 `#dispatch` 页面试运营提示可见。

## 是否完成
DONE

## 风险
- 未改派车核心逻辑。
