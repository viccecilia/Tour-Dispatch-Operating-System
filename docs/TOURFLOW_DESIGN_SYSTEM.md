# TourFlow Unified Design System

Round: R062_UI_DESIGN_SYSTEM_FOUNDATION

## Product Feeling

TourFlow should feel like a clean Japanese SaaS operations product:

- light background
- white runtime cards
- soft borders
- restrained shadows
- clear status colors
- generous but not wasteful spacing
- one primary action per workflow surface

References: SmartHR, MoneyForward, Uber Fleet, Notion spacing, Linear hierarchy.

Avoid:

- overly dark pages
- heavy gradients everywhere
- excessive outlines
- dense form walls
- mixed font weights
- raw error text

## Color Tokens

| Token | Value | Usage |
| --- | --- | --- |
| primary | `#2563eb` | Primary action, selected tab, active state |
| success | `#169456` | Completed, returned, confirmed success |
| warning | `#f59e0b` | Attention, pending operation, due soon |
| danger | `#dc2626` | Failed, blocked, expired |
| info | `#0891b2` | Location, arrived, informational state |
| background | `#eef3f8` | App/page background |
| card | `#ffffff` | Panels, runtime cards, table cards |
| surface-soft | `#f8fafc` | Inner blocks, muted inputs |
| text | `#0f172a` | Main text |
| muted | `#64748b` | Helper text, metadata |
| border | `#dbe5f0` | Card and control borders |

## Typography

| Role | Web | Miniapp |
| --- | --- | --- |
| Page title | 24-30px / 700-800 | 42rpx / 900 |
| Section title | 16-18px / 700 | 30rpx / 900 |
| Card title | 14-16px / 650-750 | 27rpx / 800 |
| Body | 14px / 400-500 | 25rpx / 400-500 |
| Muted | 12-13px / 500 | 22rpx / 500 |
| Badge | 12px / 650 | 22rpx / 700 |

Rules:

- Do not use negative letter spacing.
- Do not scale font size with viewport width.
- Keep table text compact but readable.
- Use bold only for operational decisions: route, time, count, status.

## Cards

Standard SaaS cards:

- background: white
- border: `#dbe5f0`
- radius: 24-28rpx / 14px
- shadow: soft, low opacity
- padding: 20-28rpx

Runtime Hero:

- used for the current operator/driver/task identity
- should not dominate the full screen
- can use primary gradient only for identity/status emphasis
- all secondary cards should remain white

## Buttons

Primary:

- blue for normal SaaS action
- green for irreversible operational progress such as confirm dispatch or driver next step
- one visible primary action per mobile screen

Secondary:

- white or primary-soft background
- border visible but quiet

Disabled:

- gray background
- no strong shadow

## Status Badges

| Status | Color |
| --- | --- |
| assigned / pending | primary-soft blue |
| confirmed | light cyan |
| departed | warning-soft amber |
| arrived | info-soft cyan |
| in_service | soft purple |
| completed / returned | success-soft green |
| failed / expired | danger-soft red |

## Empty / Loading / Error

No raw single-line failures.

Every runtime empty state should include:

- short title
- short explanation
- optional retry action
- no red wall unless the workflow is blocked

For miniapps use `empty-state`, `loading-state`, `error-state`.
For Web use `empty-panel` and shared error/empty components.

## Layout

Web:

- sidebar remains dark and stable
- content cards are white, light, layered
- KPI cards should be consistent height
- module errors stay inside modules

Driver Miniapp:

- current driver state first
- one primary next action
- five-tab workbench remains simple
- no sales price

Dispatcher Miniapp:

- high-volume dispatch views prefer pools and fast filters
- package/charter orders need wider table-like treatment
- driver and vehicle lists stay compact
- map is a main tab

## Implementation Entry Points

- Web: `frontend/src/styles/globals.css`
- Driver Miniapp: `miniapp/styles/theme.wxss`
- Dispatcher Miniapp: `miniapp_dispatch/app.wxss`
