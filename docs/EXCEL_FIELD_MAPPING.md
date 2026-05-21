# Excel Field Mapping

R012 aligns the MVP order model with the core fields in `Framework.xlsx`.

## Core Mapping

| Excel field | System field |
| --- | --- |
| 订单备注代码 | `order_note_code` |
| 订单来源 / 旅行社 | `order_source`, `agency_name` |
| 订单号 | `oid` |
| 车种类型 | `vehicle_class` |
| 订单类型 | `order_type` |
| 出发日期 | `order_date` |
| 出发时间 | `start_time` |
| 到达日期 | `end_date` |
| 到达时间 | `end_time` |
| 出发地点 | `pickup_location` |
| 结束地点 | `dropoff_location` |
| 客人数 | `passenger_count` |
| 行李数 | `luggage_count` |
| 司机代码 | `driver_code` |
| 语言 | `driver_language` |
| 车牌简写 | `plate_short_code` |
| 车辆类型代码 | `vehicle_type_code` |
| 颜色 | `vehicle_color` |
| 雪胎 | `snow_tire` |
| 费用备注 | `fee_remark` |
| 订单价格（人民币） | `price_rmb`, `price` |
| 订单价格（日元） | `price_jpy` |
| 代收 / 费用备注合计（日元） | `collection_amount_jpy` |
| 停车费（日元） | `parking_fee_jpy` |
| 其他费用（日元） | `other_fee_jpy` |
| 司机工资（日元） | `driver_salary_jpy` |

## Order Number Rule

Temporary unassigned order:

```text
D + YYMMDD + - + daily serial + -TMP
```

Example:

```text
D260520-0001-TMP
```

Assigned order:

```text
source code + YYMMDD + - + daily serial + - + plate short code + driver code + vehicle type code
```

Example:

```text
D260520-0001-2345LCZA
```

## Vehicle Type Code

- `A`: 3代 / Alphard / Vellfire
- `H`: 10座 / Hiace
- `C`: 18座 / 中巴
- `B`: 大巴 / Bus

## Current Limits

- R012 stores the fields but does not perform full finance settlement.
- Driver code is not yet managed through a dedicated driver profile field; when not provided, it is inferred from the driver name.
- Vehicle color and snow tire are stored but not yet used for automatic vehicle matching.
