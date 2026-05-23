# TASK-005：前端展示优化顺序

## 修改了什么
- Dispatch 页面点击“接龙排序”后使用后端返回的优化顺序更新选中订单顺序。
- 新增“路线接龙与空驶风险”卡片。
- 展示平均分、风险数量、同车多单建议、每段接龙评分和理由。

## 涉及文件
- `frontend/src/pages/DispatchPage.tsx`

## 验证方式
- `npm.cmd run build`
- `npm.cmd run lint`

## 是否完成
DONE

## 风险
- 需要人工在页面上选择多单后确认展示密度和文案是否适合调度员。
