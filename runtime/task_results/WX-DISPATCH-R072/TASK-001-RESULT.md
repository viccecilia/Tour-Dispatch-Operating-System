# TASK-001 RESULT

## 修改了什么
- 完善 runtime 配置：支持 `WX_DISPATCH_ENV=trial`、`WX_DISPATCH_TRIAL_MODE`、`WX_DISPATCH_API_HOST`、`WX_DISPATCH_API_PORT`。
- 补充 `.env.trial.example`，明确 trial 不自动 reset demo 数据。

## 涉及文件
- `.env.example`
- `.env.trial.example`
- `backend/config.py`
- `backend/app/config.py`

## 验证方式
- `python -m compileall backend scripts`
- `python scripts/init_trial_db.py`

## 是否完成
DONE

## 风险
- 真实云端域名需要部署时替换 `https://api.example.com`。
