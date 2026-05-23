# TASK-007 提醒中心与工作履历入口

## 修改了什么
- 司机端增加提醒中心折叠区。
- 司机端增加工作履历入口，支持关键词搜索。
- 后端新增司机履历查询接口。

## 涉及文件
- `backend/services/driver_service.py`
- `backend/api/routes.py`
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`

## 验证方式
- `python scripts/verify_driver_api.py` 验证 driver history 返回测试 assignment。

## 是否完成
DONE

## 风险
- 提醒类型目前复用已有通知体系，未来 30 分钟/5 分钟提醒还需要定时任务或小程序本地提醒策略。
