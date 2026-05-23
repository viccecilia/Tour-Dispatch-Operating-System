# TASK-003 入库流程页

## 修改了什么
- 入库检查项保留并明确：车辆清扫、入库点检、入库酒精测试、点呼入库。
- `点呼入库` 改为独立动作 `onReturnYard`。
- 入库提交会写入 workflow events，并提交 `return_yard` 报备。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`

## 验证方式
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 本轮只做轻量状态和报备，不做复杂审批。
