# TASK-003 我的页面

## 修改了什么
- 我的页面新增司机基本信息、电话、司机代码、语言、驾照到期、健康体检到期。
- 新增收入统计区：今日订单、今日完成、今日预计收入、本月预计收入、本月送迎、本月包车。
- 保留提醒中心、工作履历、离线补交和设置入口。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`

## 验证方式
- `node --check miniapp/pages/driver/index.js`
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 驾照到期和健康体检到期依赖司机资源表字段维护；缺失时显示 `-`。
