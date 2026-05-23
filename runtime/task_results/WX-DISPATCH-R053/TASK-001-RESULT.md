# TASK-001 Parser 错误修复

## 修改了什么
- 解析失败时在 `parse_result_json` 中增加试运营处理提示。
- 前端 Parser 页面顶部增加“试运营反馈记录点”，提示低置信度、解析失败、常改字段和确认入库流程。

## 涉及文件
- `backend/services/parser_service.py`
- `frontend/src/pages/ParserPage.tsx`
- `frontend/src/components/PilotFeedbackNote.tsx`

## 验证方式
- `python -m compileall backend scripts`
- `npm.cmd run build`
- 浏览器检查 `#parser` 页面试运营提示可见。

## 是否完成
DONE

## 风险
- 本轮不重做解析规则，只补试运营错误处理提示；真实错误样本仍需继续收集。
