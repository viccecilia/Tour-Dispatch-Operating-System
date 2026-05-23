# TASK-003 流程式拍照

## 修改了什么
- 将照片节点改成流程式展示：
  1. 到达上车点
  2. 到达等待照片
  3. 接到客人照片
  4. 中途地点照片
  5. 送达照片
  6. 行程结束
- 接到客人照片上传成功后，会继续提交 `start_service`。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`

## 验证方式
- `python scripts/verify_driver_api.py`
- 验证输出包含 `evidence_upload_success`、`waypoint_evidence_upload_success`、`dropoff_evidence_upload_success`。

## 是否完成
DONE

## 风险
- 本轮仍使用 mock/base64 上传验证，不做云存储深度集成。
