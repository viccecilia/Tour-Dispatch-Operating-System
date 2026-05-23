# Tour Dispatch Operating System

Lightweight dispatch runtime for tour vehicle operations.

## Miniapp Projects

This repository contains two WeChat Mini Program entry points:

### Driver Miniapp

- Path: `miniapp/`
- WeChat DevTools project name: `wx-dispatch-miniapp`
- Main page: `pages/driver/index`
- Purpose:
  - Driver daily workbench
  - Yard departure / return workflow
  - Driver task calendar
  - Order execution flow
  - Location and photo evidence entry points
  - Driver expenses

Open this folder in WeChat DevTools when previewing the driver-side app.

### Dispatcher Miniapp

- Path: `miniapp_dispatch/`
- WeChat DevTools project name: `wx-dispatch-dispatcher-miniapp`
- Main tabs:
  - Home
  - Import
  - Dispatch
  - Map
  - Finance
- Purpose:
  - Mobile order import
  - Batch parser correction
  - Quick dispatch
  - Driver / vehicle map view
  - Lightweight finance summary

Open this folder in WeChat DevTools when previewing the dispatcher-side app.

## Local Backend

Default local backend:

```text
http://127.0.0.1:18765
```

If WeChat DevTools blocks local API requests, enable local development mode and disable request domain validation in DevTools project settings.

## Notes

- `project.private.config.json` files are local machine settings and are intentionally not committed.
- Runtime databases, logs, caches, screenshots, and demo run outputs should not be committed unless explicitly needed for a release artifact.
