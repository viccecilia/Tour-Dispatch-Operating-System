# WX-DISPATCH-R041 司机端工作流重构与地图导航增强

## 修改了什么
- 司机端首页改为司机每日工作台，去掉运营中台式指标。
- 新增每日工作流事件、费用报备、工作履历 API。
- 扩展照片节点类型。
- 司机端增加下一步大按钮、当前订单、地图导航、照片、费用、提醒、履历、今日任务列表。
- reset demo 统计覆盖新增司机工作流和费用表。
- verify_driver_api 覆盖工作流事件、费用、履历、位置和照片。

## 验证方式
- `python -m compileall backend scripts`
- `node --check miniapp/pages/driver/index.js`
- `python scripts/reset_demo_db.py`
- `python scripts/health_check.py`
- `python scripts/verify_driver_api.py`
- `python scripts/verify_dispatch_api.py`
- `python scripts/verify_calendar_api.py`
- `cd frontend && npm.cmd run build`
- `cd frontend && npm.cmd run lint`

## 是否完成
DONE

## 风险
- 微信真机定位、拍照、导航仍需人工验收。
- Google Maps 仅预留 URL/fallback，未接 SDK。
- 费用财务确认/驳回需要后续财务端完善。
