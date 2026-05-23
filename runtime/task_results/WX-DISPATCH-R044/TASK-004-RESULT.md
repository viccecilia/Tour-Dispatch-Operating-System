# TASK-004 一单完成后进入下一单

## 修改了什么
- 新增 `onFinishCurrentOrder`：点击行程结束后提交 `complete_order`。
- 如果存在下一单，小程序会自动选中下一单并停留在任务地图页。
- 验证脚本新增第二个同司机订单，覆盖多订单司机任务场景。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `scripts/verify_driver_api.py`

## 验证方式
- `python scripts/verify_driver_api.py`
- 验证输出包含 `workbench_initial_today_orders: 2`、`next_assignment_visible: true`。

## 是否完成
DONE

## 风险
- 自动进入下一单是前端选中下一单；如果网络延迟较高，实际状态刷新仍依赖 API 返回。
