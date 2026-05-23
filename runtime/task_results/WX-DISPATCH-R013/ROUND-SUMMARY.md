# WX-DISPATCH-R013：AI Dispatch Brain v1

## 本轮结果
- 新增规则型派车推荐服务。
- 新增 `POST /api/dispatch/recommend`。
- 前端 Dispatch 页面新增“智能推荐”入口和推荐理由展示。
- 推荐结果只回填司机和车辆，人工确认后才派车。
- 验证脚本已覆盖推荐数量、推荐理由、冲突场景和原派车链路。

## 验证结果
- `python -m compileall backend scripts`：通过。
- `python scripts/verify_dispatch_api.py`：通过。
- `npm.cmd run build`：通过。
- `npm.cmd run lint`：通过。
- 浏览器派车页检查：已看到“智能推荐”入口。

## 风险
- 当前为规则型推荐，不是地图路径优化。
- 地点接龙评分依赖文本标准化质量。
- 推荐是否符合真实运营直觉需要人工验收。

## 下一轮建议
- R014 可做“调度员反馈闭环”：采用/不采用推荐、人工改派原因、推荐规则权重微调。
