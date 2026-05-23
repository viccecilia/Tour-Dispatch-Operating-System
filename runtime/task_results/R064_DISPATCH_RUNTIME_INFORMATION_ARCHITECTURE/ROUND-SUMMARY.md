# R064 DISPATCH_RUNTIME_INFORMATION_ARCHITECTURE Summary

## 修改了什么

- 调度首页改成调度待办中心，突出未派车、待确认、高风险、今日订单。
- 导入页默认折叠正常草稿，只优先展示问题草稿，支持 50-80 单导入时降低屏幕压力。
- 派车页新增顶部压力条和一键接龙入口，保留包车、接机、送机、司机、车辆和底部派车条。
- 地图页增加在线司机、即将开始、风险订单摘要。
- 财务页改为轻量财务待办，突出今日垫付、异常费用、待确认。

## 每个任务状态

- TASK-001: DONE
- TASK-002: DONE
- TASK-003: DONE
- TASK-004: DONE
- TASK-005: DONE

## 验证结果

- `node --check miniapp_dispatch/pages/index/index.js`：PASS
- `node --check miniapp_dispatch/pages/import/index.js`：PASS
- `node --check miniapp_dispatch/pages/dispatch/index.js`：PASS
- `node --check miniapp_dispatch/pages/map/index.js`：PASS
- `node --check miniapp_dispatch/pages/finance/index.js`：PASS
- `python -m json.tool miniapp_dispatch/app.json > $null`：PASS
- `python -m compileall backend scripts`：PASS
- `python scripts/health_check.py`：PASS
- `python scripts/reset_demo_db.py`：PASS
- `python scripts/verify_dispatch_mobile_runtime.py`：PASS
- `python scripts/verify_dispatch_mobile_pilot.py`：PASS
- `python scripts/verify_shared_orders_sync.py`：PARTIAL，通知计数口径不一致：shared-state API 返回 notifications=0，DB 直接计数为 97。

## 协作验收结果

需要人工在微信开发者工具确认：

- 首页是否更像调度待办中心
- 导入页风险草稿折叠是否适合 50-80 单
- 派车页四块结构是否清楚
- 地图页风险摘要是否有用
- 财务页是否够轻量

## 未完成/风险

- 风险计算目前偏显示层，未做严格迟到/未确认/异常费用规则引擎。
- `verify_shared_orders_sync.py` 的通知计数和 shared-state API 口径不一致，需要后续修复接口统计。
- 真机滑动、卡片密度、底部派车条是否遮挡内容，需要人工确认。

## 下一轮建议

- R065：Dispatch Miniapp Visual QA，打开首页、导入、派车、地图、财务逐页截图，按真实 50-80 单场景调整密度和滚动窗口。
