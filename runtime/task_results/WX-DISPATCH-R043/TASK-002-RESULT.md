# TASK-002 出库流程页

## 修改了什么
- 出入库页新增独立出库状态摘要：车辆状态、清扫状态、酒精测试状态。
- 出库检查项保留并明确：车灯、刹车、车身损伤、驾照、乘务员证、酒精确认、睡眠是否充足。
- `点呼出库` 改为独立动作 `onDepartYard`，不再复用首页下一步按钮。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`

## 验证方式
- `node --check miniapp/pages/driver/index.js`
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 如果订单仍是 `assigned`，小程序会提示先到首页确认接单，再点呼出库，避免跳过司机确认。
