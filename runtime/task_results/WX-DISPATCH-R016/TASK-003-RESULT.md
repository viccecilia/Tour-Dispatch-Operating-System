# TASK-003：空驶风险提示

## 修改了什么
- 接龙段落按分数输出 `low / medium / high` 风险。
- 明显地点差异、时间重叠、时间过紧会降低分数并提示风险。
- route summary 返回 `risk_count` 和提示 message。

## 涉及文件
- `backend/services/dispatch_service.py`
- `frontend/src/pages/DispatchPage.tsx`

## 验证方式
- 额外 API 验证返回：
  - `risk_count: 1`
  - message: `发现 1 段空驶或时间风险，请人工确认后再派车。`

## 是否完成
DONE

## 风险
- 空驶风险是规则提示，不是公里数或分钟级路线规划。
