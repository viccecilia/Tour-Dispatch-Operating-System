# TourFlow 测试账户

版本：2026-06-03
目标：本地和云端使用同一套测试账户；同一登录名在 Web 和小程序端使用同一密码。

## 访问地址

| 端口 | 本地 Web | 云端 Web |
| --- | --- | --- |
| 平台总控 / 车公司 Web | `http://127.0.0.1:5173/` | `https://admin-trial.taxi-airport.jp/` |
| 旅行社 Web | `http://127.0.0.1:5173/#agency-portal` | `https://admin-trial.taxi-airport.jp/#agency-portal` |
| API | `http://127.0.0.1:18765` | `https://api-trial.taxi-airport.jp` |

## 平台总控 Web

| 入口 | 登录名 | 密码 |
| --- | --- | --- |
| 平台总控 Web | `admin` | `admin123` |

## 车公司端 Web / 小程序管理账号

| 公司代码 | 公司名 | 管理账号 | 调度账号 | 运行管理账号 | 旧管理账号 | 旧调度账号 | 旧运行账号 | 密码 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SKR | Sakura Fleet | `SKR-08070010000` | `SKR-08070010001` | `SKR-08070010002` | `SKR-admin` | `SKR-dispatch` | `SKR-ops` | `Test123456` |
| KEX | Kansai Express | `KEX-08070020000` | `KEX-08070020001` | `KEX-08070020002` | `KEX-admin` | `KEX-dispatch` | `KEX-ops` | `Test123456` |
| TYO | Tokyo Premium | `TYO-08070030000` | `TYO-08070030001` | `TYO-08070030002` | `TYO-admin` | `TYO-dispatch` | `TYO-ops` | `Test123456` |

## 车公司司机账号

| 公司 | 司机代码 | 司机名 | 电话 | 登录名 | 密码 |
| --- | --- | --- | --- | --- | --- |
| SKR | SKR-D01 | Ken Sato | 080-7001-0101 | `SKR-08070010101` | `Test123456` |
| SKR | SKR-D02 | Aki Tanaka | 080-7001-0102 | `SKR-08070010102` | `Test123456` |
| SKR | SKR-D03 | Ryo Suzuki | 080-7001-0103 | `SKR-08070010103` | `Test123456` |
| KEX | KEX-D01 | Yuki Mori | 080-7002-0101 | `KEX-08070020101` | `Test123456` |
| KEX | KEX-D02 | Hiro Ito | 080-7002-0102 | `KEX-08070020102` | `Test123456` |
| KEX | KEX-D03 | Nao Kato | 080-7002-0103 | `KEX-08070020103` | `Test123456` |
| TYO | TYO-D01 | Shun Watanabe | 080-7003-0101 | `TYO-08070030101` | `Test123456` |
| TYO | TYO-D02 | Mai Kobayashi | 080-7003-0102 | `TYO-08070030102` | `Test123456` |
| TYO | TYO-D03 | Ren Yamada | 080-7003-0103 | `TYO-08070030103` | `Test123456` |

## 旅行社 Web / 小程序 Portal 登录

| 旅行社代码 | 旅行社名 | 登录代码 | 密码 |
| --- | --- | --- | --- |
| AGA | Toyo Holiday Travel | `AGA2026` | `Test123456` |
| AGB | Fuji Tour Travel | `AGB2026` | `Test123456` |
| AGC | Keihan International Travel | `AGC2026` | `Test123456` |

## 旅行社内部角色账号

管理和客服用于旅行社 Web / 小程序权限测试；财务角色当前保留账号数据，前端可按管理端视图合并。

| 旅行社 | 管理账号 | 客服账号 | 财务账号 |
| --- | --- | --- | --- |
| AGA | `080-7101-0000` / `Test123456` | `080-7101-0001` / `Test123456` | `080-7101-0002` / `Test123456` |
| AGB | `080-7102-0000` / `Test123456` | `080-7102-0001` / `Test123456` | `080-7102-0002` / `Test123456` |
| AGC | `080-7103-0000` / `Test123456` | `080-7103-0001` / `Test123456` | `080-7103-0002` / `Test123456` |

## 旅行社导游账号

| 旅行社 | 导游 | 登录名 | 密码 |
| --- | --- | --- | --- |
| AGA | Mico Yamamoto | `080-7101-0101` | `Test123456` |
| AGA | Naomi Kuroda | `080-7101-0102` | `Test123456` |
| AGA | Sho Hayashi | `080-7101-0103` | `Test123456` |
| AGB | Gayun Lee | `080-7102-0101` | `Test123456` |
| AGB | Emily Childers | `080-7102-0102` | `Test123456` |
| AGB | Mahesh Patil | `080-7102-0103` | `Test123456` |
| AGC | Noki Shi | `080-7103-0101` | `Test123456` |
| AGC | Donghan Yang | `080-7103-0102` | `Test123456` |
| AGC | Mina Okada | `080-7103-0103` | `Test123456` |

## 说明

- 车公司 Web 和车公司小程序使用同一套账号密码。
- 旅行社 Web 和旅行社小程序使用同一套账号密码。
- 旧车公司账号仍保留，便于回归测试；新账号以 `公司代码-手机号数字` 为主。
- 微信小程序源码更新后，需要用微信开发者工具重新上传版本，手机端才会看到最新 UI。
