# TASK-001 结果

状态：DONE

修改了什么：

- 新增 `scripts/demo_seed.py`，一次性生成接近真实运营的演示数据。
- demo seed 覆盖手工订单、parser 草稿确认订单、批量派车、多司机执行报备。
- 回归脚本调整为使用专用司机/车辆，避免历史 active assignment 导致测试冲突。

涉及文件：

- `scripts/demo_seed.py`
- `scripts/verify_dispatch_api.py`
- `scripts/verify_calendar_api.py`
- `scripts/verify_driver_api.py`

验证方式：

- `python scripts/demo_seed.py`
- `python scripts/verify_orders_api.py`
- `python scripts/verify_dispatch_api.py`
- `python scripts/verify_calendar_api.py`
- `python scripts/verify_parser_api.py`
- `python scripts/verify_driver_api.py`

是否完成：是

风险：

- demo seed 会追加数据，不会清空旧数据。
