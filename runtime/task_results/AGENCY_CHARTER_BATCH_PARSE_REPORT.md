# 旅行社后台包车批量解析验证报告

## 范围

- 新增旅行社后台“批量包车解析”入口。
- 支持多行包车文本一行一单解析。
- 覆盖用户样例中的日期、时间、路线、往返路线、车型、绿牌、价格、客人姓名、司机要求备注。
- 批量导入时透传 `vehicle_color`，旅行社订单列表也返回该字段。

## 修改文件

- `backend/services/agency_portal_service.py`
  - `parse_agency_order_text` 支持 `charter_batch` / `batch_charter`。
  - 新增紧凑包车行解析逻辑，识别 `6.02 09:00 京都往返天桥立美山 包车 3代 绿1900Mico Yamamoto` 这类文本。
  - 创建旅行社订单时写入 `vehicle_color`。
  - 旅行社订单列表查询返回 `o.vehicle_color`。
- `frontend/src/pages/AgencyPortalPage.tsx`
  - 批量入单页增加“解析包车批量”和“填入包车示例”按钮。
  - 导入预览的车型列显示 `车型 + 车辆颜色`。
- `frontend/src/services/apiClient.ts`
  - `parseAgencyPortalOrders` 增加 `charter_batch` 模式。
  - 修正请求 header 合并顺序。
  - 为旅行社 token 增加模块内缓存，并对 `/api/agency-portal` 请求统一补 `X-Agency-Token`。

## 本地验证

### 后端服务级验证

命令：

```powershell
python - <<'PY'
# 使用 runtime/test_dbs/agency_charter_batch_parse.sqlite3
# 调用 parse_agency_order_text + create_agency_order
PY
```

结果：

- 6 条样例全部解析成功。
- 6 条解析结果全部为 `order_type=charter`。
- 第一单解析为 `2026-06-02 09:00 京都 -> 京都 3代 绿牌 Mico Yamamoto 1900`。
- 第二单保留 `司机KAKAO联系` 备注。
- 第四单解析为 `10座 绿牌 乃綺 施 1600`。
- 第六单解析为 `京都 -> 大阪 10座 绿牌 Emily Childers 1700`，备注保留 `英文司机`。
- 6 条订单均创建成功，旅行社订单列表可取回 6 个 `vehicle_color=绿牌`。

### 编译与构建

命令：

```powershell
python -m py_compile backend\services\agency_portal_service.py backend\api\routes.py
npm.cmd run build
```

结果：

- Python 编译通过。
- 前端 TypeScript + Vite 构建通过。
- Vite 仍提示单个 chunk 超过 500 kB，这是既有体积提示，不阻断构建。

### 浏览器页面验证

验证地址：

- `http://127.0.0.1:5173/#agency-portal`

结果：

- 页面可见“批量入单”页签。
- 页面可见“解析机场接送”“解析包车批量”“填入包车示例”按钮。
- 点击“填入包车示例”后，文本框填入 6 条包车样例。
- 点击“解析包车批量”后，页面显示“已解析 6 条包车订单。”
- 预览表显示：
  - `Mico Yamamoto`
  - `Gayun Lee`
  - `Mahesh Patil`
  - `乃綺 施`
  - `Donghan Yang`
  - `Emily Childers`
- 车型列显示 `3代 绿牌` 或 `10座 绿牌`。
- “批量导入 6 单”按钮变为可用。

截图：

- `runtime/task_results/agency_charter_batch_parse_browser.png`

## 运行说明

- 未做云端部署。
- 未 Git push。
- 未上传小程序。
- 未修改生产数据库。
- 浏览器验证时发现原本运行的本地 `runtime/wx_dispatch.sqlite3` 在重启初始化时存在 `orders.oid` 唯一约束冲突。为避免清理或修改现有数据，浏览器验证使用了临时测试库：
  - `runtime/test_dbs/agency_browser_verify.sqlite3`
