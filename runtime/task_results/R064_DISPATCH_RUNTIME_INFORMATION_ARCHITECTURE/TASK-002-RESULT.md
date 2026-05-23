# TASK-002 Import Runtime Simplification

- 导入页改为风险优先：正常草稿默认折叠，只展示问题草稿和少量可入库预览。
- 增加“已折叠”计数，避免一次导入 50-80 单时满屏铺开。
- 涉及文件：
  - `miniapp_dispatch/pages/import/index.js`
  - `miniapp_dispatch/pages/import/index.wxml`
  - `miniapp_dispatch/pages/import/index.wxss`
- 验证方式：
  - `node --check miniapp_dispatch/pages/import/index.js`
  - `python scripts/verify_dispatch_mobile_runtime.py`
- 状态：DONE
- 风险：草稿风险规则仍沿用现有前端字段检查，复杂解析准确率不在本轮范围。
