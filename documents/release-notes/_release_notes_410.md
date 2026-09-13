# FlaskToolkit v4.10.0 — Accessibility

**Community Edition** — architecture-scaled for small LAN / personal use. Community continues active maintenance and feature iteration; **Enterprise Edition (5.x)** carries the long-term enterprise roadmap and is **publicly seeking a new maintainer** (see [Enterprise Edition handover & roadmap](https://github.com/ReconLeo/FlaskToolkit/blob/main/documents/Enterprise-Edition-%E4%BA%A4%E6%8E%A5%E4%B8%8E%E8%B7%AF%E7%BA%BF.md)).

Release theme: **Accessibility** — lowering the bar for individual users and small LANs to install, configure, onboard and manage plugins.

## What's new since v4.9.2

### v4.10.0 — Accessibility

- **Standalone pip-dependency declaration (`pip_dependencies`, M1)**: `dependencies` now means *plugin* dependencies only; Python packages move to the new `pip_dependencies` field (plugin.json / class attribute / AST extraction / description consistency). Missing packages only skip that plugin with a warning plus the exact `pip install` command (no auto-install); legacy 3.x-style mixed declarations are still detected with a migration warning.
- **Pre-install capability checklist (M2)**: admin upload is now two-phase — `preview=1` parses the package and returns a capability preview (dependencies / pip deps / capabilities / static-scan summary) plus a `preview_id`; `confirm=1&preview_id` actually installs. The old direct-install flow still works; fixed the `finally` cleanup bug that could delete preview files.
- **Per-plugin API doc pages, admin-only (M3)**: `build_api_info` is now shared and annotates the `permission` level (route declaration → view_func `@permission` → default user); a new `/__plugin_api__/<name>` route opens the debug page for **any** plugin, not just bare ones; debug routes moved under the admin guard (guest 302 / normal user 403 / admin 200); three-color permission badges on the API page plus an "API docs" button on every plugin row.
- **First-run wizard + forced password change (M4)**: `/setup` wizard (LANGUAGE whitelist) with a `data/.setup_done` marker — the home page redirects to `/setup` until completed; auth gained self-service password change (`change_password` verifies the old password, kicks other sessions, keeps the current one; `POST /api/auth/change-password`); login responses carry `must_change_pwd` while the default password is still in use, and the admin UI shows a change-password dialog on every load until it is changed (dismissible, but it comes back).
- **Invite-code self-registration (M5)**: `ALLOW_REGISTER` switch (default off); one-time invite codes `FTK-XXXXXXXX-XXXX` (stored in `plugins/data/auth/invite_codes.json`, `used_by` marks one-shot consumption); holders skip review, everyone else lands in the pending queue for admin approval; `login` blocks pending accounts (403); user management gained 6 admin APIs (pending list / approve / reject / generate invite / copy register link / revoke); `/register?code=` pre-fills the code, and the login page shows a register entry when enabled.
- **Plugin scaffolding + offline install (M6)**: `tools/scaffold.py` generates standard skeletons — backend (plugin.json + BasePlugin main .py + optional templates/static) and frontend (config.json + entry html + optional static) — ready to be packaged directly; `tools/install_plugin.py` installs plugins **without running the framework** (integrity check / description consistency / framework version / static-scan gate → secure extraction + installed_files manifest → pip-missing hints); same-name installs are refused, `--update` upgrades without downgrades; `list` subcommand and `--base` to point at a framework root.
- **Offline uninstall + per-plugin storage cleanup (M6-Extra)**: `cleanup_plugin_data()` in the core — temp-only (`plugins/temp/<name>/`) or all data (`plugins/data/<name>/` + temp + capabilities `filesystem:write` declared dirs such as AirDrop `uploads/`; offline resolution from the descriptor file, normcase safety guard); `POST /api/admin/plugins/<name>/purge-data` (`scope: temp|all`, quota-cache invalidation + audit log); the system page's Plugin Storage card now has **Clean Temp / Purge All** buttons per plugin; `install_plugin.py uninstall backend|frontend <name> [--purge-data]` (built-ins protected, data cleaned before files are removed); Factory Reset also clears non-built-in plugin data directories.
- **Regression suite: 28 scripts / 737 assertions**, all green — new `test_setup` (17), `test_register` (25), `test_scaffold_tools` (53); `test_pack_meta` 19→22, `test_admin_api` 28→44, `test_framework_fixes` 9→12, `test_factory_reset` 37→39.

## Asset

| File | SHA-256 |
|------|---------|
| `FlaskToolkit-4.10.0-runtime.zip` | `e381b84745a1c448dc334fc44241191632605b0d0aea9afa219cbe20c567f773` |

Upgrade hint: keep your `data/`, `plugins/` (user plugins) and custom templates — the runtime package contains the framework code only. Built-in `locales/` language packs (zh-CN/en) ship inside the package and are upgraded in place; any custom `locales/<lang>.json` you added are preserved. The runtime package now also ships `tools/` (scaffold / install-plugin / update / backup / reset CLI).
