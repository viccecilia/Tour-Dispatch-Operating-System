# TASK-005 费用报备与代收款入口

## 修改了什么
- 新增司机费用报备表。
- 支持司机垫付和司机代收两类记录。
- 小程序端增加费用类别、金额、说明、提交入口。
- Driver Workbench 统计今日待提交费用。

## 涉及文件
- `backend/db/schema.sql`
- `backend/db/database.py`
- `backend/services/driver_service.py`
- `backend/api/routes.py`
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `scripts/verify_driver_api.py`

## 验证方式
- `python scripts/verify_driver_api.py` 验证 expense 创建、查询、workbench 待提交费用。

## 是否完成
DONE

## 风险
- 费用与财务最终确认/驳回的完整闭环后续还需要财务端继续接入。
