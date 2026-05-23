# TASK-001：关键运营提醒自动生成

## 修改了什么
- 新增运营提醒扫描逻辑。
- 自动生成以下提醒：
  - 未确认订单
  - 未出库
  - 未到达
  - 未上传照片
  - 未提交费用
  - 未入库
- 同一业务对象使用 `source_type + source_id` 去重，避免重复刷屏。

## 涉及文件
- `backend/services/notification_service.py`

## 验证方式
- `python scripts/verify_driver_api.py`
- 额外查询 `/api/notifications/summary` 和 `/api/notifications`

## 是否完成
- DONE

## 风险
- 提醒阈值为当前轻量规则，频率和提前时间需要运营试用后再调。
