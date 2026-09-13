# FlaskToolkit v4.9.2

**Community Edition** — architecture-scaled for small LAN / personal use. Community continues active maintenance and feature iteration; **Enterprise Edition (5.x)** carries the long-term enterprise roadmap and is **publicly seeking a new maintainer** (see [Enterprise Edition handover & roadmap](https://github.com/ReconLeo/FlaskToolkit/blob/main/documents/Enterprise-Edition-%E4%BA%A4%E6%8E%A5%E4%B8%8E%E8%B7%AF%E7%BA%BF.md)).

## What's new since v4.8.0

### v4.9.2 — CI fixes + global data quota + storage dashboard
- **CI compatibility fixes** (GitHub Actions was failing on Python 3.10/3.11, passing on 3.12):
  - PEP 701 f-string nested same-quote calls (`f"{_tr()("...")}"`) are 3.12+ only → rewritten with single-quote nesting (3.6+ compatible); an `ast.parse(feature_version=(3, 10))` syntax check is now part of the release checklist to prevent regressions
  - Upload temp dir `UPLOAD_TEMP_DIR` now created at module level (+ upload fallback), fixing `FileNotFoundError` on the test-client path
  - GitHub Actions bumped to Node 24: `checkout@v6` / `setup-python@v6` / `upload-artifact@v6`
- **Global total data quota**: `PLUGIN_DATA_TOTAL_LIMIT_MB` (default `0` = unlimited) caps the *sum of all plugin data* — `quota.total_limit_mb()` + `check_upload` auto-wiring + audit-hook global dimension (single-plugin cap + global total, `enforce` blocks / `observe` logs)
- **Admin storage dashboard**: `GET /api/admin/quota` + a "Plugin Storage" card on the system page — per-plugin limit/usage/remaining plus the global total row
- Regression suite: **25 scripts / 612 assertions**, all green

### v4.9.1 — Declarative storage quota
- New `storage` domain in capabilities (`storage:limit:<size>`): plugins request storage authorization, overriding the global default; quota scope auto-extends to `filesystem:write` declared paths (e.g. AirDrop `uploads/`)
- Upload pre-check API (`check_upload`, 413 + remaining space) plus audit-hook fallback
- Example updates: `async_file_demo` showcases quota, `corp_tools` showcases multilingual UI

### v4.9.0 — i18n + plugin data quota
- **i18n framework**: lightweight JSON language packs (zh-CN + en built-in, extensible by adding `locales/<lang>.json`; plugins can ship their own packs merged into the lookup chain); unified `t()` across templates / backend / frontend (`window.T`); `LANGUAGE` config for startup language + per-user cookie switching
- **Per-plugin data quota** (`PLUGIN_DATA_LIMIT_MB`, default 50 MB, `0` = disabled) enforced by the runtime audit hook — `observe` logs / `enforce` blocks writes under `plugins/data/<name>/` and `plugins/temp/<name>/`

## Asset

| File | SHA-256 |
|------|---------|
| `FlaskToolkit-4.9.2-runtime.zip` | `641a21ddbe8ea506ae1e429b5b4cd9e4359ed7120aad0dae1c119b893291c20f` |

Upgrade hint: keep your `data/`, `plugins/` (user plugins), `config.json`, `locales/` and custom templates — the runtime package contains the framework code only.
