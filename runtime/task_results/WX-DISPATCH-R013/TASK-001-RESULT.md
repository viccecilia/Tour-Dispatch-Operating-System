# TASK-001：AI Dispatch Brain 后端推荐服务

## 修改了什么
- 新增规则型派车推荐服务，不接 OpenAI，不自动派车落库。
- 根据选中订单、可用司机、可用车辆生成推荐组合。
- 推荐结果包含 score、reasons、conflicts。

## 涉及文件
- `backend/services/dispatch_brain_service.py`
- `backend/api/routes.py`

## 验证方式
- `python -m compileall backend scripts`
- `python scripts/verify_dispatch_api.py`

## 是否完成
DONE

## 风险
- 当前是轻量规则评分，地点接龙只做文本相似和顺序提示，不等同地图路径最优。
- 服务复用了 `dispatch_service` 内部 helper，后续可整理为公共冲突检测模块。
