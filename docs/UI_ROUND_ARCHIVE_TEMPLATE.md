# UI Round Archive Template

每个 UI Round 结束后，必须形成一份可对比的视觉归档。

## 目录规范

```text
docs/ui_snapshots/<Round ID>/
├── web-dashboard.png
├── web-dispatch.png
├── web-calendar.png
├── web-driver-monitor.png
├── web-finance.png
├── web-analytics.png
├── web-automation.png
├── web-settings.png
├── miniapp-driver-home.png
├── miniapp-driver-yard.png
├── miniapp-driver-map.png
├── miniapp-driver-expense.png
├── miniapp-driver-profile.png
└── UI_SNAPSHOT_REPORT.md
```

## Web 自动截图

```bash
python scripts/capture_web_snapshots.py
```

可通过环境变量指定轮次和地址：

```bash
set WX_DISPATCH_UI_ROUND=R058
set WX_DISPATCH_FRONTEND_URL=http://127.0.0.1:5173
set WX_DISPATCH_BASE_URL=http://127.0.0.1:18765
python scripts/capture_web_snapshots.py
```

## 小程序手动截图

参考：

```text
docs/MINIAPP_SCREENSHOT_GUIDE.md
```

## 报告生成

```bash
python scripts/generate_ui_snapshot_report.py
```

## 报告必须包含

- 截图文件列表
- 页面说明
- 本轮视觉变化
- 人工备注区
- 未解决视觉问题
- 下一轮 UI 建议

## 人工验收建议

- 页面是否还有大面积空白。
- 主要动作是否足够明显。
- 表格是否拥挤。
- 移动端按钮是否适合点击。
- 错误状态是否看起来像产品状态，而不是程序崩溃。
