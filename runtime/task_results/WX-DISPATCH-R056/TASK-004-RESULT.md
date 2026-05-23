# TASK-004：运营助手页面骨架补齐

## 修改了什么
- 运营助手接口失败时进入“离线模式”，仍显示今日运营摘要卡、KPI、AI 建议区域、风险提醒、未派车提醒、司机异常摘要。
- 无建议时显示 EmptyPanel。
- 保留“建议可解释、不自动派车、不自动改财务”的页面定位。

## 涉及文件
- `frontend/src/pages/CopilotPage.tsx`

## 验证方式
- `npm run build`
- `npm run lint`
- 浏览器检查 `http://127.0.0.1:5173/#copilot`

## 是否完成
DONE

## 风险
- 运营助手仍是规则解释型建议，不接真实 AI。
