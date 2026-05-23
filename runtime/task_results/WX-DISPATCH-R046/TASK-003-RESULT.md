# TASK-003 下一步大按钮强化

## 修改了什么
- 新增底部固定主动作按钮，位于底部 Tab 上方。
- 首页动作卡弱化为说明，主动作统一由固定按钮承载。
- 出入库和行程结束按钮降级为辅助按钮，减少多个主按钮抢焦点。

## 涉及文件
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`

## 验证方式
- `node --check miniapp/pages/driver/index.js`

## 是否完成
DONE

## 风险
- 费用页和我的页不显示主动作 dock，避免和费用提交/设置入口冲突。
