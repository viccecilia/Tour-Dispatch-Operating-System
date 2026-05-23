# TASK-004：司机链路回归

## 修改了什么
- 保持司机 API 主链路不变。
- 离线逻辑只在小程序端处理，不改后端报备接口。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/utils/offlineQueue.js`

## 验证方式
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 脚本验证的是后端司机链路，不能替代微信端断网人工测试。
