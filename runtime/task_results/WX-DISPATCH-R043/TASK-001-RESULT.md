# TASK-001 Dashboard 司机化

## 修改了什么
- 保留 R042 五页结构，继续优化司机端首页 Dashboard。
- 首页只放司机关心的信息：司机姓名、日期时间、当前状态、今日订单、下一单时间、本月送迎、本月包车、本月事故、待提交费用。
- 没有恢复运营中台指标，也没有显示订单销售价格。

## 涉及文件
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.js`

## 验证方式
- `node --check miniapp/pages/driver/index.js`
- WXML 扫描未出现 `price`、`价格`、`售价`、`订单价格`。

## 是否完成
DONE

## 风险
- 需要微信开发者工具人工确认实际移动端视觉。
