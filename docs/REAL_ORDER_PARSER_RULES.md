# Real Order Parser Rules

## Scope

R011 migrates the first batch of real dispatch parsing rules into the current WX Dispatch runtime.

The parser is still rule-based. It does not use external AI services.

## Location Normalization

Locations are stored in `locations`:

- `std_name`
- `loc_type`
- `aliases`

The seed process loads:

- built-in common Kansai/Japan dispatch locations
- `Framework.xlsx` `location-data` sheet when available at the known local path

Examples:

- `关西` / `关空` / `KIX` / `关西机场` -> `KIX`
- `大阪` / `大阪市内` / `Osaka` -> `大阪市`
- `京都` / `京都市内` -> `京都市`
- `环球` / `USJ` -> `环球影城`

## Date Rules

Supported examples:

- `3.29` -> `2026-03-29`
- `5.09` -> `2026-05-09`
- `260530` -> `2026-05-30`
- `20260530` -> `2026-05-30`
- `5月10日` -> `2026-05-10`

## Time Rules

Supported examples:

- `10:30` -> `10:30`
- `1030` -> `10:30`
- `08:00/20:00` -> start `08:00`, end `20:00`

Bare four-digit values are treated carefully to avoid reading prices such as `1900` as time.

## Vehicle Type Rules

Supported examples:

- `3代`, `埃尔法`, `阿尔法`, `ALPHARD` -> `3代`
- `10座`, `海狮`, `HIACE` -> `10座`
- `绿`, `绿牌` -> `绿牌`

Current storage uses existing `vehicle_type`; R012 should split this into richer fields.

## Note Tokens

Supported examples:

- `儿童座椅`
- `儿童座椅*2`
- `婴儿座椅`
- `接机牌`
- `深夜`
- `航班`
- `轮椅`
- `代收2000日元`
- parenthesized fee notes such as `（+座椅2000）`

Notes are preserved in `remark`.

## Route Rules

Supported examples:

- `大阪往返天桥立美山`
- `大阪-奈良-宇治-京都`
- `大阪单送名古屋`
- `关西接机大阪`
- `京都送机关西`
- `环球往返接送`

Multi-stop chains are preserved in `remark` as `路线链`.

## Known Limits

- The parser does not yet split a large pasted paragraph into multiple orders. That is planned for R013.
- Financial details are not yet split into RMB, JPY, collection fee, parking fee, other fee, and driver salary. That is planned for R012.
- `vehicle_type` is still a combined text value such as `10座 绿牌`.
