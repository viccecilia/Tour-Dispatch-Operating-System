# TASK-005：费用页去表单化

## 修改了什么
- 费用页顶部改为两个大入口：新增垫付、新增代收。
- 费用表单默认折叠，点击入口后展开。
- 费用记录改为记录流展示，保留状态 badge。
- 提交成功后自动收起表单。

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
- 本轮没有新增照片小票真实上传，只保留现有费用提交链路。
