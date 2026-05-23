# TASK-002 结果：Dispatch Console Runtime Feeling

## 修改了什么
- 派车页顶部增加 `LIVE DISPATCH` Runtime 区。
- 展示未派车、已选择、已派车、未确认等运营态指标。
- 去掉页面顶部试运行提示块，减少后台提示感。

## 涉及文件
- `frontend/src/pages/DispatchPage.tsx`
- `frontend/src/styles/globals.css`

## 验证方式
- `cd frontend && npm.cmd run build`
- `cd frontend && npm.cmd run lint`

## 是否完成
DONE

## 风险
- 派车核心交互未重构，本轮只增强页面运营感和状态感。
