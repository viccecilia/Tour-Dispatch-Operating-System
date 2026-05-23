# TASK-003：派车建议 API

## 修改了什么
- 新增 `POST /api/dispatch/recommend`。
- 请求参数：`order_ids`。
- 返回：`success`、`order_ids`、`recommendations`。
- recommendations 每项包含：driver、vehicle、score、reasons、conflicts。

## 涉及文件
- `backend/api/routes.py`
- `frontend/src/services/apiClient.ts`
- `frontend/src/types/api.ts`

## 验证方式
- `python scripts/verify_dispatch_api.py`

## 是否完成
DONE

## 风险
- API 只给推荐，不做落库。人工仍需点击派车确认，这是本轮设计边界。
