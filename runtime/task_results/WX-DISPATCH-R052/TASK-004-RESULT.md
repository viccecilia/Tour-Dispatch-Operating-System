# TASK-004 Orders evidence viewer

## 修改了什么
- Orders 页面增加“执行证据”列。
- 点击“查看证据”后，在订单表上方展开证据链面板。
- 证据面板显示照片、报备、小票/费用统计和最近 timeline。

## 涉及文件
- `frontend/src/pages/OrdersPage.tsx`
- `frontend/src/services/apiClient.ts`

## 验证方式
- `npm.cmd run build`
- `npm.cmd run lint`
- 浏览器打开 `http://127.0.0.1:5173/#orders` 确认“执行证据”入口可见。

## 是否完成
DONE

## 风险
- 未派车订单没有 assignment 时会显示空证据链，这是预期行为。
