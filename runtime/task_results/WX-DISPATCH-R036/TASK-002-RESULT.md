# TASK-002：司机端照片入口

## 修改了什么
- 小程序司机端增加照片凭证区。
- 支持三类照片：
  - 接客照片
  - 完成照片
  - 车况照片
- 支持查看已上传记录并预览图片。

## 涉及文件
- `miniapp/pages/driver/index.js`
- `miniapp/pages/driver/index.wxml`
- `miniapp/pages/driver/index.wxss`
- `miniapp/utils/api.js`

## 验证方式
- `node --check miniapp/pages/driver/index.js`

## 是否完成
DONE

## 风险
- 微信 `chooseImage` 和 `previewImage` 需要在开发者工具或真机人工验收。
