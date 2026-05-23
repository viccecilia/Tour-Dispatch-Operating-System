# TASK-005 验证脚本

## 修改了什么
- 扩展 `scripts/verify_driver_api.py`：
  - 验证 assignment evidence timeline 可查询。
  - 验证订单 evidence chain 可查询。
  - 验证照片数、费用数、下载文件数。

## 涉及文件
- `scripts/verify_driver_api.py`

## 验证方式
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 脚本使用 mock base64 图片，不代表真实微信上传链路的文件质量。
