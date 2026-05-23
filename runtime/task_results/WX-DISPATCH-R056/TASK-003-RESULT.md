# TASK-003：自动化页面骨架补齐

## 修改了什么
- 自动化页面 API 失败时保留规则列表、触发条件、动作区域、执行策略区域。
- 最近执行日志 API 失败时只在日志模块内提示，不影响整页。
- loading 使用规则 SkeletonCard。

## 涉及文件
- `frontend/src/pages/AutomationPage.tsx`

## 验证方式
- `npm run build`
- `npm run lint`
- 浏览器检查 `http://127.0.0.1:5173/#automation`

## 是否完成
DONE

## 风险
- 规则编辑仍沿用现有启停和运行能力，本轮没有新增规则配置业务。
