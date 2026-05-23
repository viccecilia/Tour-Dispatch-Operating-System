# TASK-006 文档与验证

## 修改了什么
- 新增司机端 UI 规范文档。
- 完成 R046 要求的编译、健康检查、司机 API、派车 API、小程序 JS 检查。

## 涉及文件
- `docs/DRIVER_UI_GUIDELINES.md`
- `runtime/task_results/WX-DISPATCH-R046/`

## 验证方式
- `python -m compileall backend scripts`
- `python scripts/reset_demo_db.py`
- `python scripts/health_check.py`
- `$env:PYTHONIOENCODING='utf-8'; python scripts/verify_driver_api.py`
- `python scripts/verify_dispatch_api.py`
- `node --check miniapp/pages/driver/index.js`

## 是否完成
DONE

## 风险
- 真机地图权限、openLocation 和复制 URL 需要在微信开发者工具或真机中人工确认。
