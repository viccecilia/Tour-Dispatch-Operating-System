# 小程序截图归档指南

微信小程序页面不能像普通 Web 页面一样稳定用 Playwright 自动截图。司机端截图建议通过微信开发者工具手动保存，再放入统一目录。

## 目标目录

默认归档目录：

```text
docs/ui_snapshots/R055/
```

如果是新一轮 UI 调整，把 `R055` 换成本轮编号，例如 `R058`。

## 需要截图的司机端页面

请按以下文件名保存：

- `miniapp-driver-home.png`：司机首页
- `miniapp-driver-yard.png`：出入库页
- `miniapp-driver-map.png`：任务地图页
- `miniapp-driver-expense.png`：费用页
- `miniapp-driver-profile.png`：我的页面

## 操作步骤

1. 打开微信开发者工具。
2. 打开项目目录 `miniapp/`。
3. 确认后端 API 地址已配置到 `miniapp/utils/api.js`。
4. 编译后进入司机端页面。
5. 分别切换底部五个 Tab。
6. 在模拟器区域截图。
7. 按上面的文件名保存到 `docs/ui_snapshots/<Round ID>/`。
8. 运行：

```bash
python scripts/generate_ui_snapshot_report.py
```

## 截图建议

- 使用同一个设备尺寸，例如 iPhone 14 Pro Max。
- 每轮 UI 对比尽量保持相同缩放比例。
- 若页面需要滚动，优先截首屏；重要长页面可追加 `-bottom` 文件，例如 `miniapp-driver-map-bottom.png`。
- 截图前先清缓存并重新编译，避免旧页面残留。

## 验收点

- 首页是否像司机工作台。
- 出入库 Step 是否清楚。
- 地图页是否像导航入口。
- 费用页是否不像后台表单。
- 我的页面是否像个人中心。
