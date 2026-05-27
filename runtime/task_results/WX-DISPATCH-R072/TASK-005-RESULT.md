# TASK-005 RESULT

## 修改了什么
- 新增 trial 数据库初始化脚本。
- trial 数据库清空交易数据，不使用 demo 累加数据。
- 内部测试账号初始化：admin / dispatcher / operations_manager / driver。
- 保留 `zongzou` 超级微信测试号配置。

## 涉及文件
- `scripts/init_trial_db.py`

## 验证方式
- `python scripts/init_trial_db.py`

## 是否完成
DONE

## 风险
- 真实司机、车辆来源依赖当前本地资源库；如果本地库缺真实车牌，trial 需要先导入车辆。
