# 三人测试计划 HTML 部署报告

日期：2026-05-31

## 部署内容

- 本地文件：`runtime/task_results/THREE_PERSON_FULL_TEST_PLAN.html`
- 服务器文件：`/var/www/tourflow-admin/test/three-person-test-plan.html`
- 访问地址：`https://admin-trial.taxi-airport.jp/test/three-person-test-plan.html`
- 页面内测试入口已更新为：
  - Web：`https://admin-trial.taxi-airport.jp`
  - 旅行社 Web：`https://admin-trial.taxi-airport.jp/#agency-portal`
  - API：`https://api-trial.taxi-airport.jp/api/ping`

## 验证结果

- SSH 登录 Sakura VPS 成功。
- 服务器静态目录 `/var/www/tourflow-admin` 可写。
- 已创建目录 `/var/www/tourflow-admin/test`。
- 已上传 HTML 文件。
- 远端文件大小：`52425` bytes。
- HTTPS 访问返回：`HTTP 200`。
- 2026-05-31 复传后确认页面中不再出现 `127.0.0.1:5173`。
- 2026-06-01 追加修复：重新构建并上传前端静态文件，构建时设置 `VITE_API_BASE_URL=https://api-trial.taxi-airport.jp`，避免 `admin-trial/api/*` 被前端路由误返回 `index.html`。

## 说明

当前页面为静态 HTML。三台电脑都可以访问同一个 URL，但填写结果保存在各自浏览器的 `localStorage` 中，不会自动汇总到服务器。

如果需要三个人共享同一份实时测试进度，需要追加后端测试结果保存接口和数据库表。
