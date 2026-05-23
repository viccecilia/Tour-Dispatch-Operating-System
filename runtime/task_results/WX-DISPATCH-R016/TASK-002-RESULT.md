# TASK-002：起终点接龙评分

## 修改了什么
- 每段接龙返回 `score`、`risk`、`reasons`、`time_gap_minutes`。
- 地点接龙评分基于起终点文本归一化、别名和地点 token 重合度。
- 支持关空/KIX/关西机场、大阪/Osaka 等轻量别名归一。

## 涉及文件
- `backend/services/dispatch_service.py`

## 验证方式
- 额外 API 验证返回示例：
  - `酒店（国贸） -> 酒店（国贸）`
  - `score: 100`
  - `risk: low`
  - 理由包含时间间隔和地点匹配。

## 是否完成
DONE

## 风险
- 文本相似不能替代真实地图距离。
