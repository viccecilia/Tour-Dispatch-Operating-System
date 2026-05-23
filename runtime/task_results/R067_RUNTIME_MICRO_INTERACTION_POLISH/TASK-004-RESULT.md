# TASK-004 结果：Card / Table Interaction

## 修改了什么
- Web Card 默认加入 `micro-surface`，鼠标悬停时有轻微浮起和阴影变化。
- 表格行增加统一 hover 状态。
- Runtime pill 增加轻量 hover 反馈。

## 涉及文件
- `frontend/src/components/ui/card.tsx`
- `frontend/src/styles/globals.css`

## 验证方式
- `cd frontend && npm.cmd run build`
- `cd frontend && npm.cmd run lint`

## 是否完成
DONE

## 风险
- 表格密度和列布局没有在本轮改动。
