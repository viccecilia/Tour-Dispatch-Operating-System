# 旅行社后台标准行程 PDF 入口调整报告

## 需求

标准 PDF 行程资料应绑定在每个具体行程 / 订单上维护，不放在“发布到订单大厅”的发布表单里。

## 修改内容

- `frontend/src/pages/AgencyPortalPage.tsx`
  - “订单跟踪”表格新增“标准行程 PDF”列。
  - 每条订单 / 行程行内显示：
    - 当前 PDF 文件名或“未上传”
    - “查看”链接
    - “上传 PDF”按钮
  - “发布到订单大厅”面板移除 PDF 文件上传框。
  - 发布面板保留提示：标准行程 PDF 在“订单跟踪”的每个行程中维护，发布到大厅只公开基础行程、车型和价格。
  - 上传成功提示从订单大厅消息改为行程级提示。

## 验证

### 前端构建

命令：

```powershell
npm.cmd run build
```

结果：

- TypeScript 和 Vite 构建通过。
- Vite 仍提示单个 chunk 超过 500 kB，这是既有体积提示，不阻断构建。

### 接口验证

使用临时本地测试库：

- `runtime/test_dbs/agency_browser_verify.sqlite3`

验证步骤：

- 登录旅行社门户。
- 创建测试订单 `A260620-0001-TMP`。
- 调用 `/api/agency-portal/orders/1/itinerary-pdf` 上传 `standard-itinerary-test.pdf`。
- 再调用 `/api/agency-portal/orders`，确认订单返回：
  - `itinerary_pdf_name=standard-itinerary-test.pdf`
  - `itinerary_pdf_url=/uploads/agency_itineraries/...standard-itinerary-test.pdf`

结果：

- 行程级 PDF 上传链路正常。

### 浏览器验证

地址：

- `http://127.0.0.1:5173/#agency-portal`

结果：

- “订单跟踪”页每条行程都有“标准行程 PDF”列和“上传 PDF”按钮。
- 已上传订单显示 `standard-itinerary-test.pdf` 和“查看”链接。
- “订单大厅”发布面板不再出现文件上传框。
- “订单大厅”文件输入框数量为 `0`。

截图：

- `runtime/task_results/agency_pdf_per_itinerary_browser.png`

## 安全边界

- 未做云端部署。
- 未 Git push。
- 未上传小程序。
- 未清理或修改生产数据。
- 浏览器验证使用临时测试库，不处理原本本地 `runtime/wx_dispatch.sqlite3` 的数据冲突。
