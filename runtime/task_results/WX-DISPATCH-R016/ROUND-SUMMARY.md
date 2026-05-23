# WX-DISPATCH-R016：Route Optimization Engine

## 本轮结果
- 接龙建议从简单 `handoff` 升级为路线优化结果。
- 返回按时间排序后的订单顺序。
- 每段接龙包含分数、风险、原因、时间间隔。
- 提示空驶风险和同车多单建议。
- Dispatch 页面展示“路线接龙与空驶风险”卡片。

## 验证结果
- `python -m compileall backend scripts`：通过。
- `python scripts/verify_dispatch_api.py`：通过。
- `npm.cmd run build`：通过。
- `npm.cmd run lint`：通过。
- 额外路线建议验证：3 单返回 2 段接龙，包含 `average_score`、`risk_count`、`same_vehicle_suggestion`、每段 reasons。

## 风险
- 当前不接地图 API，不计算真实距离和路程时间。
- 空驶风险基于地点文本相似和时间间隔，需调度员人工判断。
- 系统只给建议，不自动改派车结果。

## 下一轮建议
- 引入地点库坐标或区域码，不接外部地图也能先做区域级距离评分。
- 增加司机/车辆历史常跑区域，提高同车多单推荐质量。
