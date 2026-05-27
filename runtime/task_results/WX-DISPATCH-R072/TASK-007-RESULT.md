# TASK-007 RESULT

## 修改了什么
- 新增 trial health check。
- 检查 trial DB、API ping、登录、driver、dispatch、finance admin API。

## 涉及文件
- `scripts/health_check_trial.py`

## 验证方式
- `python scripts/health_check_trial.py`

## 是否完成
DONE

## 风险
- 如果云端 Web URL 未设置，Web 后台检查会跳过，需要部署时设置 `WX_DISPATCH_WEB_URL`。
