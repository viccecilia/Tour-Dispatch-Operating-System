# TASK-004 Photo Flow Simplification

- 保留现有“当前上传点”逻辑，只显示当前需要处理的照片节点。
- 未到达或未进入状态的照片节点不再铺开展示。
- 涉及文件：
  - `miniapp/pages/driver/index.wxml`
- 验证方式：
  - `python scripts/verify_driver_api.py`
- 状态：DONE
- 风险：照片是否强制上传、距离校验是否严格，需要后续按运营规则继续细化。
