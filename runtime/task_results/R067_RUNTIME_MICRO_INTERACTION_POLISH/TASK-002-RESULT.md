# TASK-002 结果：Loading / Skeleton 稳定化

## 修改了什么
- `SkeletonCard` 改为 shimmer 骨架屏。
- 统一错误、空状态、重试按钮文案为中文。
- Error / Empty / Skeleton 组件增加轻量进入动效。

## 涉及文件
- `frontend/src/components/OperationalState.tsx`
- `frontend/src/styles/globals.css`

## 验证方式
- `cd frontend && npm.cmd run build`
- `cd frontend && npm.cmd run lint`

## 是否完成
DONE

## 风险
- 只统一了现有共用组件，个别页面自写的 loading 文案还可后续继续替换。
