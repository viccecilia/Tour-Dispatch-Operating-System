# TASK-006 我的页面视觉升级

## 修改了什么
- 我的页改为调度员个人中心。
- 展示调度员姓名、代码、角色、接口地址、共享数据库同步状态。
- 操作入口保留刷新同步状态和退出登录。

## 涉及文件
- `miniapp_dispatch/pages/profile/index.wxml`
- `miniapp_dispatch/pages/profile/index.wxss`

## 验证方式
- `node --check miniapp_dispatch/pages/profile/index.js`

## 是否完成
DONE

## 风险
- 个人中心仍是轻量版；后续可加入账户绑定、权限说明和设备状态。
