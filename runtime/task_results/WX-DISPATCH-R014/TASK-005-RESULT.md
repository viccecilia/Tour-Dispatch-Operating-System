# TASK-005：资源验证脚本

## 修改了什么
- 新增 `scripts/verify_resources_api.py`。
- 覆盖新增司机、新增车辆、编辑司机、编辑车辆、提醒计算、dashboard 资源提醒。

## 涉及文件
- `scripts/verify_resources_api.py`

## 验证方式
- `python scripts/verify_resources_api.py`

## 是否完成
DONE

## 风险
- 验证脚本会写入 R014 测试资源；正式演示前可运行 reset/demo 脚本重置。
