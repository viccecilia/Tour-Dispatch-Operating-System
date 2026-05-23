# TASK-001：location_logs 表

## 修改了什么
- 新增 `location_logs` 表结构。
- 数据库初始化和兼容迁移会确保旧库也具备位置日志表。

## 涉及文件
- `backend/db/schema.sql`
- `backend/db/database.py`

## 验证方式
- `python -m compileall backend scripts`
- 位置 smoke 调用写入 `location_logs` 成功。

## 是否完成
DONE

## 风险
- 当前只保存最新和历史位置日志，不做轨迹回放。
