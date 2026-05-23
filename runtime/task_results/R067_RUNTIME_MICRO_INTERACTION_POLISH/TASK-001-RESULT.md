# TASK-001 结果：Motion Token 与页面过渡

## 修改了什么
- 在 Web 全局样式中新增 `runtime-page`、`runtime-fade-up`、`runtime-page-in` 动画。
- 页面主内容区增加轻量进入过渡。
- 支持 `prefers-reduced-motion`，减少动画敏感用户的不适。

## 涉及文件
- `frontend/src/styles/globals.css`
- `frontend/src/layouts/SaasShell.tsx`

## 验证方式
- `cd frontend && npm.cmd run build`
- `cd frontend && npm.cmd run lint`

## 是否完成
DONE

## 风险
- 动画只做轻量进入，不做复杂页面切换动画。
