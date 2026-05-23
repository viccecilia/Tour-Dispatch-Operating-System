# TASK-004：司机链路回归

## 修改了什么
- 本轮没有改后端司机接口。
- 保持报备、位置、照片、通知主链路不变。

## 涉及文件
- `miniapp/pages/driver/index.js`

## 验证方式
- `python scripts/verify_driver_api.py`

## 是否完成
DONE

## 风险
- 自动化验证只能覆盖后端链路，语音播放需要人工验收。
