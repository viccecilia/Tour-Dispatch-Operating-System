# WX Dispatch React Admin Console

正式 SaaS Admin Console，独立于 `backend/` 和 `miniapp/` 运行。

## Local Dev

```bash
cd frontend
npm install
npm run dev
```

默认地址：

- Frontend: http://127.0.0.1:5173
- Backend API: http://127.0.0.1:18765

如需切换 API：

```bash
copy .env.example .env
```

然后修改：

```text
VITE_API_BASE_URL=http://127.0.0.1:18765
```

## Build

```bash
npm run build
npm run lint
```

## Pages

- Dashboard
- Parser
- Orders
- Dispatch
- Calendar
- Driver Monitor
- Vehicles
- Finance
- Settings
