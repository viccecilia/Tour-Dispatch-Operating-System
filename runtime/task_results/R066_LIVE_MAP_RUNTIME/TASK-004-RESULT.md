# TASK-004 结果：Risk Highlight

## 修改了什么
- 地图 marker 增加风险高亮。
- 位置超过 15 分钟未刷新时标红。
- 结合 `/api/driver/safety-alerts`，高风险/严重异常司机也会标红。
- 右侧增加“风险高亮”列表。

## 涉及文件
- `frontend/src/pages/MapPage.tsx`

## 验证方式
- `python scripts/verify_live_map_runtime.py`
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 当前风险来自位置过期和已有司机安全告警；未加入复杂规则，例如长时间静止、偏航、未按时到达。
