# FlaskToolkit

<p align="center">
  <img src="https://github.com/ReconLeo/FlaskToolkit/actions/workflows/ci.yml/badge.svg" alt="CI">
  <img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
  <img src="https://img.shields.io/badge/version-4.9.2-blue" alt="Version">
</p>

> A Flask-based plugin **framework**: bring scattered Python plugins and pure-frontend tools into one unified runtime —
> dynamically installable, hot-reloadable, permission-controlled. Self-written, self-maintained, runs only on your own machine.

> **English**: this page · **中文**：[中文](README.zh-CN.md)

## Why FlaskToolkit (Author's Story)

I have written a lot of "little things": sign-in scripts, scheduled tasks, file handlers, chart pages… Most are in Python, many are Flask pages with the frontend and backend in one, and quite a few are pure-frontend HTML. Each works well on its own, but they are scattered across folders — every time I wanted to add a feature, I had to reinvent login/auth, upload/download, page skeletons, and scheduled jobs from scratch.

What bothered me even more: more and more things that should stay lightweight were being pushed online — unusable offline, and quietly collecting my data. I did not want to register an account and accept a privacy policy just to use an internal mini tool. What I wanted were small programs running on my own computer (at most shared with a few people on a LAN).

So FlaskToolkit was born: a plugin **framework** — not another run-of-the-mill tools site — that packs my "private little apps", along with their capabilities, into one reusable and extensible foundation.

Over time it grew into what it is today — a few highlights:

- **Plugin ecosystem**: from single-file plugins to **plugin packages (.zip)** (templates + static assets, install and go); pure-frontend HTML tools as first-class citizens; large plugins split into **multi-template + helper modules + static assets** with their own sub-pages (`page=True`);
- **Permission & security**: unified three-level permissions, optional auth, audit logs, hot reload; layered defense — **AST static scanning (4.3.1) → capability cross-validation (4.3.2) → runtime audit hooks (4.4.0)**; login-failure lockout with manual unlock; optional HTTPS;
- **Unified file transfer**: global upload-size ceiling (100MB, per-route overridable) with pre-save streaming checks, RFC 5987 Chinese-safe downloads, download stats & Range resume;
- **Plugin data quota system**: per-plugin data limit (4.9.0) → declarative `storage:limit` override (4.9.1) → **global total cap + admin storage dashboard** (4.9.2);
- **i18n**: lightweight JSON language packs (zh-CN + en built-in, extensible by adding `locales/<lang>.json`), unified `t()` across templates/backend/frontend, `LANGUAGE` startup config + per-user cookie switching (4.9.0);
- **Ops & tooling**: version check with a `changelog.json` feed + dual-backend updater (git / archive), Factory Reset, backup/restore, startup self-check, package integrity signing, plus a **615-assertion regression suite and GitHub Actions CI**.

The full feature specification lives in the [development guide](documents/Flask插件框架开发规范-v4.0.md).

To be honest, this framework's goal is not to "reinvent Django": it stands on the shoulders of giants like Flask, APScheduler, and Werkzeug, and lands the parts I needed. Its trust model is blunt — **installing a plugin means trusting its author**: plugins run in-process with the framework, without sandboxing (see dev guide 10.1). But it does not stop at "bare trust": layered defense — **static scanning (4.3.1) → capability cross-validation (4.3.2) → runtime audit hooks (4.4.0)** — sits on top, together with optional HTTPS (4.5.0) and login lockout/manual unlock (4.3.0/4.5.1) and project branding / customizable system name (4.7.0) plus version check & dual-backend update tooling (4.8.0) and i18n / declarative storage quota (4.9.1) / global quota & storage dashboard (4.9.2). That is enough for trusted LANs / enterprise intranets running daily tools; exposing to an adversarial public network still needs your own risk assessment (plugins are still unsandboxed).

My only principle: **need-driven, whatever is convenient**. So what you get is an out-of-the-box, low-barrier toolbox that lets you drop in tools whenever you want, with your data always in your own hands.

## What It Is

A Flask-based plugin **framework** (self-hosted runtime):

- Both **backend plugins (Python)** and **frontend tools (HTML packages)** can be dynamically installed / updated / uninstalled / enabled / disabled;
- Auth is an **optional plugin** — skip it for guest mode, install it for login / permission control;
- File-watching hot reload, changes take effect immediately;
- Built-in admin panel (dashboard / plugin management / logs / stats / system reset).

In one sentence: this is a **plugin framework** — a unified home for your local mini programs, plus a "foundation" you never have to rewrite.

## Quick Start

```bash
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000` in your browser (local-only by default; set `FLASKTOOLKIT_HOST=0.0.0.0` for LAN use, see below).

On first run, install the built-in `auth` plugin to enable auth; default admin account `admin / admin123` (editable in `plugins/configs/auth.json`).

Want to feel the fun of "installing plugins" right away? Install the official examples:

```bash
pip install -r requirements.txt -r requirements-dev.txt   # install_all.py needs requests
python examples/install_all.py                            # install all 7 official examples
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASKTOOLKIT_HOST` | `127.0.0.1` | Bind address; local-only by default, use `0.0.0.0` for LAN |
| `FLASKTOOLKIT_PORT` | auto-detect | Explicit port; falls back if occupied |
| `FLASKTOOLKIT_DEBUG` | off | Debug mode; do not enable in production |

## Official Examples

The [`examples/`](examples/README.md) directory ships with a set of one-click installable examples that demonstrate the full framework, and serve as starting templates for new plugin development:

| Example | Type | Highlights |
|---------|------|-----------|
| `hello_plugin` | Backend plugin | Lifecycle hooks, three-level permissions, config read/write, custom page |
| `scheduler_demo` | Backend plugin | APScheduler scheduled jobs (interval/cron) |
| `async_file_demo` | Backend plugin | Upload limits, async tasks, status polling, result download |
| `dependent_demo` | Backend plugin | Dependency declaration, cross-plugin calls |
| `multitool_demo` | Backend plugin | Large plugin multi-template: page routes, helper .py, static assets |
| `corp_tools` | Backend plugin | Enterprise-intranet kit: scheduled health probing + network-whitelist capabilities, permission-filtered navigation, notice board |
| `dashboard_demo` | Frontend tool | Admin permission, calls backend APIs, ECharts, static assets |

See [examples/README.md](examples/README.md).

## Documentation

Detailed specs live in the [Flask Plugin Framework Development Guide](documents/Flask插件框架开发规范-v4.0.md) (plugin development, permission model, frontend-tool spec, plugin-package format, security design, ops tools):

- [Official examples guide](examples/README.md)
- [Flask Plugin Framework Roadmap](documents/Flask插件框架-Roadmap-v4.1.md)
- [Version wrap-up checklist](documents/版本收尾-checklist.md)
- [GitHub Actions setup & open-source publishing guide](documents/GitHub-Actions-上手与开源发布指南.md)
- [Enterprise Edition handover & roadmap (v5.x)](documents/Enterprise-Edition-交接与路线.md)

## Tests & CI

`tests/` contains **25 scripts / 615 assertions** of regression tests (isolated-directory mode, no pollution of project files); GitHub Actions runs them automatically on Python 3.10 / 3.11 / 3.12, covering permissions, plugin-package / frontend-tool chains, integrity signatures, uninstall manifests, Factory Reset, large-plugin multi-template page routing, file transfer (upload limits / Chinese-name downloads / Range), static security scanning, capability cross-validation, runtime audit hooks, i18n framework, plugin data quota, ops tools, etc.

<details>
<summary>Expand: 25 test scripts</summary>

```bash
cd FlaskToolkit
python tests/test_permission.py            # permission system 20 assertions
python tests/test_stage2.py                # security hardening regression 19
python tests/test_zip_slip.py              # plugin-package zip slip 19
python tests/test_pack_meta.py             # plugin-package meta consistency 17
python tests/test_reload_race.py           # hot-reload race 1 (20 rounds)
python tests/test_meta_e2e.py              # plugin-package meta end-to-end 10
python tests/test_frontend_zip_slip.py     # frontend-tool zip slip 21
python tests/test_frontend_chain.py        # frontend-tool chain end-to-end 23
python tests/test_admin_api.py             # admin API 27
python tests/test_factory_reset.py         # Factory Reset scope 37
python tests/test_error_pages.py           # error-code pages 12
python tests/test_package_sign.py          # integrity verification / signing 22
python tests/test_plugin_cleanup.py        # uninstall installed_files manifest 23
python tests/test_frontend_permission.py   # frontend-tool access control 25
python tests/test_tools_ops.py             # ops tools backup/reset/config 19
python tests/test_page_router.py           # large-plugin multi-template page routing + pure-API no-name plugin debug page regression 21
python tests/test_framework_fixes.py       # framework small fixes: public_page exemption + CSRF single-injection 9
python tests/test_file_transfer.py         # file transfer: global 413 / plugin & route upload limits / Chinese-name downloads / download stats / Range / on_ready order 12
python tests/test_security.py              # system security: headers / cookie hardening / idle timeout / login lockout & manual unlock 45
python tests/test_plugin_scan.py           # plugin static scanning (v4.3.1): risky imports/calls/obfuscation/network+file touchpoints 35
python tests/test_capabilities.py          # plugin capability declarations (v4.3.2): parse/match/cross-check/runtime authorization 57
python tests/test_audit_hook.py            # runtime audit hooks (v4.4.0): event mapping/stack attribution/observe/enforce 38
python tests/test_update_checker.py     # update checker (v4.8.0): version compare / feed cache TTL / archive verify chain / zip-slip guard 40
python tests/test_i18n.py                  # i18n (v4.9.0): language packs / lookup chain / lang resolution / cookie switch / template render 28
python tests/test_data_limit.py            # plugin data quota (v4.9.0-4.9.2): path judge / usage / storage:limit declaration / write-dir scope / upload pre-check / global total / TTL / disable 32
# total: 25 scripts / 615 assertions
```

</details>

## Edition Status

- **Community Edition (v4.x)**: feature development continues with a deliberately controlled architectural scale, focused on small-LAN / personal-use scenarios; we maintain and release regularly (25 scripts / 615 assertions regression + CI).
- **Enterprise Edition (v5.x)**: planned to carry the long-term roadmap (refined permission model, process-level sandboxing, stricter CSP, enterprise identity integration, etc.). Due to limited team capacity, we are openly looking for maintainers to take over — see the [Enterprise Edition handover & roadmap](documents/Enterprise-Edition-交接与路线.md).

## Known Limitations

- **Security model is "install a plugin = trust its author"**: plugins run in-process with the framework, without sandboxing, and can reach the framework's full filesystem/network surface; only install plugins from trusted sources. Static scanning / capability declarations / runtime audit hooks are **risk-mitigation tools, not absolute isolation** (see dev guide 10.1).
- With that defense in depth, the recommended use is: **local machine or a trusted LAN / enterprise intranet** (pair with the `auth` plugin; optionally enable `PLUGIN_SCAN_MODE=enforce` and `AUDIT_HOOK_MODE=enforce`; for HTTPS see `tools/gen_cert.py`).
- Not hardened for adversarial public networks — **not recommended for direct public exposure**; if you must, put a gateway/reverse-proxy in front and assess the risk yourself.
- For LAN use, set `FLASKTOOLKIT_HOST=0.0.0.0`, pair it with the `auth` plugin, and assess the risk yourself.

## License & Contributing

MIT License · contribution guidelines in [CONTRIBUTING.md](CONTRIBUTING.md) · AI-assisted development was used; see the statement below.

### AI-Assisted Development Statement

This project used AI-assisted programming tools during development, including but not limited to: code generation and refactoring, code review, test case authoring, and documentation writing. All AI-assisted content has been manually reviewed by the developer and is only merged after passing the project's own regression suite (`tests/`, 540 assertions) and startup integrity self-check.

Transparency conventions for contributors:

- Using AI-assisted tools is allowed, but you are fully responsible for the **correctness, security, and compliance** of your submitted code.
- AI-generated code must pass the project's regression tests and code review (see `CONTRIBUTING.md`).
- If a PR relies heavily on AI-generated content, please note it in the PR description to help maintainers review.

## Star History

Track the growth of this project with [Star History](https://www.star-history.com/?repos=ReconLeo%2FFlaskToolkit&type=date&legend=top-left).

<a href="https://www.star-history.com/?repos=ReconLeo%2FFlaskToolkit&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=ReconLeo/FlaskToolkit&type=date&theme=dark&legend=top-left&sealed_token=6DvZLa9sIvE1KVbLXbIdgQXFE-1hZ_BUK3nyhvtBdgg9TJIBWUD7X5e7VJa30UFnoIUGHciUofZ_Uu8rRfwUbJI_JFPNcma79J0rlrHUOPVqSr4u_4KItnn5bQPeSiWWr2kC6WYkRO63hCndr-wiCz8ie9PIvzXqZiX21cg8T1-Z9PzDSAoMzqFROHAP" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=ReconLeo/FlaskToolkit&type=date&legend=top-left&sealed_token=6DvZLa9sIvE1KVbLXbIdgQXFE-1hZ_BUK3nyhvtBdgg9TJIBWUD7X5e7VJa30UFnoIUGHciUofZ_Uu8rRfwUbJI_JFPNcma79J0rlrHUOPVqSr4u_4KItnn5bQPeSiWWr2kC6WYkRO63hCndr-wiCz8ie9PIvzXqZiX21cg8T1-Z9PzDSAoMzqFROHAP" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=ReconLeo/FlaskToolkit&type=date&legend=top-left&sealed_token=6DvZLa9sIvE1KVbLXbIdgQXFE-1hZ_BUK3nyhvtBdgg9TJIBWUD7X5e7VJa30UFnoIUGHciUofZ_Uu8rRfwUbJI_JFPNcma79J0rlrHUOPVqSr4u_4KItnn5bQPeSiWWr2kC6WYkRO63hCndr-wiCz8ie9PIvzXqZiX21cg8T1-Z9PzDSAoMzqFROHAP" />
 </picture>
</a>
