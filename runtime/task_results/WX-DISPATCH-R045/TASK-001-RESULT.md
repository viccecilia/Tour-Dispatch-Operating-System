# TASK-001 费用页独立展示

## 修改了什么
- 费用页保持独立 Tab。
- 垫付类别：停车费、高速费、门票、其他。
- 代收类别：代收车费、夜班加班费、婴儿座椅费、接机费用、其他。
- 费用状态：未提交、已提交财务、财务确认、财务驳回、仍在司机手中。

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
- 本轮不做完整财务审核流，状态由司机端先提交记录。
