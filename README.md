# FlaskToolkit

<p align="center">
  <img src="https://github.com/ReconLeo/FlaskToolkit/actions/workflows/ci.yml/badge.svg" alt="CI">
  <img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
  <img src="https://img.shields.io/badge/version-4.17.2-blue" alt="Version">
</p>

> A Flask-based plugin **framework**: bring scattered Python plugins and pure-frontend tools into one unified runtime —
> dynamically installable, hot-reloadable, permission-controlled. Self-written, self-maintained, runs only on your own machine.

> **English**: this page · **中文**：[中文](README.zh-CN.md)

## Why FlaskToolkit (Author's Story)

I have written a lot of "little things": sign-in scripts, scheduled tasks, file handlers, chart pages… Most are in Python, many are Flask pages with the frontend and backend in one, and quite a few are pure-frontend HTML. Each works well on its own, but they are scattered across folders — every time I wanted to add a feature, I had to reinvent login/auth, upload/download, page skeletons, and scheduled jobs from scratch.

What bothered me even more: more and more things that should stay lightweight were being pushed online — unusable offline, and quietly collecting my data. I did not want to register an account and accept a privacy policy just to use an internal mini tool. What I wanted were small programs running on my own computer (at most shared with a few people on a LAN).

The breaking point was my own **Kaleido question-bank system**: a single-file Flask app that had grown past 3,600 lines, with dozens of API routes bolted together — adding a feature meant touching login, uploads, pages and jobs all over again. All the friction I had been accumulating finally exploded there, and many of FlaskToolkit's design ideas are a direct continuation of Kaleido's DNA: permission-aware API design, data-integrity checks, tools packaged for one-click delivery. Kaleido itself later moved onto this framework as three backend plugins plus a packaged frontend tool — the design's first real stress test. It is open source too: [github.com/ReconLeo/Kaleido](https://github.com/ReconLeo/Kaleido).

So FlaskToolkit was born: a plugin **framework** — not another run-of-the-mill tools site — that packs my "private little apps", along with their capabilities, into one reusable and extensible foundation.

Over time it grew into what it is today — a few highlights:

- **Plugin ecosystem**: single-file plugins grow into **`.zip` plugin packages** (templates + static assets, install and go); pure-frontend HTML tools are first-class citizens; large plugins split into multi-template + helper modules + static assets with their own sub-pages.
- **Permissions & defense in depth**: unified three-level permissions (public / user / admin), optional auth, audit logs, hot reload; layered protection — **AST static scanning → capability cross-validation → runtime audit hooks**; login-failure lockout; optional HTTPS.
- **Unified file transfer**: global upload-size ceiling with pre-save checks, Chinese-safe downloads (RFC 5987), download stats & Range resume.
- **Data quota system**: per-plugin quota → declarative `storage:limit` → **global total cap + admin storage dashboard**.
- **i18n**: lightweight JSON language packs (built-in zh-CN + en, extensible), one `t()` across templates / backend / frontend, and a per-page language switcher with translation tooling.
- **Low-friction onboarding**: first-run wizard with forced password change, invite-code self-registration, per-plugin API doc pages, per-plugin storage cleanup, and optional `pip_dependencies` that degrade gracefully.
- **Secure transport**: self-signed HTTPS with automatic **HTTP→HTTPS 308 redirect** and auto-configured Secure cookies — stale `http://` links never die.
- **Reachability**: an admin **Network & Access** page (share links + QR codes, mDNS, IP-change detection) plus a double-click desktop launcher for local-only vs LAN sharing.
- **Mobile**: same-URL, server-side UA-detected **dedicated mobile templates** — a plugin opts in by simply dropping same-named templates in a `mobile/` namespace.
- **Statistics**: a dashboard that answers “what’s actually going on” — runtime badge, cold-plugin hints, 14-day request trend, error Top list, and a per-user / per-IP access profile.
- **Root domain & marketplace groundwork**: plugins can declare a `framework` capability tier (`read` / `manage` / `core`, `core` ≈ root) with audited writes, backed by a programmatic plugin-management service layer and per-plugin update feeds.
- **Event bus & true dependency resolution**: a lightweight in-process pub/sub bus lets plugins talk without knowing who’s listening; dependencies resolve with version constraints and cycle detection.
- **Ops & tooling**: version check + dual-backend updater, Factory Reset, backup/restore, startup self-check, integrity signing, plugin scaffolding & offline install/uninstall CLI, plus a **43-script regression suite and GitHub Actions CI**.

The full feature specification lives in the [development guide](documents/Flask-Plugin-Framework-Dev-Guide-v4.md).

To be honest, this framework's goal is not to "reinvent Django": it stands on the shoulders of giants like Flask, APScheduler, and Werkzeug, and lands the parts I needed. Its trust model is blunt — **installing a plugin means trusting its author**: plugins run in-process with the framework, without sandboxing (see dev guide 10.1). The **`framework:core`** permission (v4.15) is the one explicit escalation beyond that — an explicit, audited **root** grant for plugins that need to modify/delete the framework's own files, marked with a loud badge and shipped under the MIT license (author takes no responsibility for damage caused by such high-risk operations). Beyond "bare trust", the framework layers on defense — static scanning, capability cross-validation, runtime audit hooks — plus optional auth / HTTPS and data-quota controls, enough for trusted LANs and intranet teams running daily tools. Exposing it to an adversarial public network still needs your own risk assessment (plugins remain unsandboxed).

My only principle: **need-driven, whatever is convenient**. So what you get is an out-of-the-box, low-barrier toolbox that lets you drop in tools whenever you want, with your data always in your own hands.

## What It Is

A self-hosted Flask plugin **framework** that turns scattered Python scripts and pure-frontend HTML tools into a unified, extensible runtime on your own machine:

- **Plugins are first-class**: backend **Python plugins** and **frontend HTML toolkits** install / update / uninstall / enable / disable at runtime — as single files or `.zip` packages carrying templates, static assets, and even sub-pages; file-watching **hot reload** applies changes instantly, and a dependency resolver orders plugins with version constraints.
- **Auth is optional**: skip it for a guest-mode workspace, or install the `auth` plugin for login + three-level permission control (public / user / admin) with audit logs.
- **Built-in admin panel**: dashboard, plugin management, logs, statistics, network & access, and system reset — plus per-plugin and global **data quotas**.
- **Unified file transfer**: global upload limits with pre-save checks, Chinese-safe downloads, download stats and Range resume.
- **Internationalized by design**: JSON language packs, a single `t()` across templates / backend / frontend, and per-page language switching.
- **Safety rails**: AST static scanning → capability cross-validation → runtime audit hooks, optional HTTPS, login lockout — enough for trusted LANs and intranet teams.
- **Ops tooling**: backup / restore, Factory Reset, startup self-check, dual-backend (git / archive) updates, plugin scaffolding, and offline install / uninstall.
- **Run it your way**: local-only (`127.0.0.1`) by default, or LAN-share with `FLASKTOOLKIT_HOST=0.0.0.0`; a desktop launcher, mDNS and one-click HTTPS make it painless.

In one sentence: a **plugin framework** — one unified home for your local mini programs, on a “foundation” you never have to rewrite.

## Who Is It For

**Personal users** — a private toolbox on your own machine:

- Default setup is local-only (`127.0.0.1`); your data stays on your disk and never leaves your machine;
- Auth is optional: skip it for a guest-mode personal workspace, or install it if you want login protection;
- No command line? Run `python tools/desktop_launcher.py` for a small GUI that starts/stops the server, picks local-only vs LAN-sharing, and copies your access address (the QR code lives on the admin **Network & Access** page);
- Start from the official examples, then drop your own scripts in as plugins whenever the need arises;
- Get into the habit of `python tools/backup.py create` before big changes.

**LAN / small-team users** — share internal tools within a trusted network:

- Set `FLASKTOOLKIT_HOST=0.0.0.0` so colleagues can reach the service over the LAN;
- Install the `auth` plugin and hand out accounts — the three-level permission model (public / user / admin) decides what each person can see and change;
- For sensitive traffic, generate an HTTPS certificate with `python tools/gen_cert.py` (or place the service behind a reverse proxy);
- Keep it up to date with `python tools/update.py` (git backend for open-source repos, archive backend for offline intranets);
- Remember the trust model: only install plugins from authors you trust.

## Quick Start

```bash
pip install -r requirements.txt
python app.py

Or, if you prefer a GUI: `python tools/desktop_launcher.py` (start / stop the server, pick local-only or LAN-sharing, copy the access address).
```

Open `http://127.0.0.1:5000` in your browser (local-only by default; set `FLASKTOOLKIT_HOST=0.0.0.0` for LAN use, see below).

On first run, install the built-in `auth` plugin to enable auth; default admin account `admin / admin123` (editable in `plugins/configs/auth.json`).

Want to feel the fun of "installing plugins" right away? Install the official examples:

```bash
pip install -r requirements.txt -r requirements-dev.txt   # install_all.py needs requests
python examples/install_all.py                            # install all 8 official examples (7 backend + 1 frontend tool)
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASKTOOLKIT_HOST` | `127.0.0.1` | Bind address; local-only by default, use `0.0.0.0` for LAN |
| `FLASKTOOLKIT_PORT` | auto-detect | Explicit port; falls back if occupied |
| `FLASKTOOLKIT_DEBUG` | off | Debug mode; do not enable in production |

## Official Examples

The [`examples/`](examples/README.md) directory ships with a set of one-click installable examples that demonstrate the full framework, and serve as starting templates for new plugin development:

| Example | Type | One-liner | Capabilities shown |
|---------|------|-----------|--------------------|
| `hello_plugin` | Backend | Scaffold: lifecycle hooks, permissions, config, custom page | hot-reload · permissions · lifecycle · config |
| `scheduler_demo` | Backend | APScheduler jobs (interval/cron) + the v4.16 event bus | scheduled jobs · event bus · async events |
| `async_file_demo` | Backend | Async tasks, upload limits, result download, storage quota | async · upload limits · quota |
| `dependent_demo` | Backend | Dependency resolution, cross-plugin calls & event subscription | dependency resolution · cross-plugin · events |
| `multitool_demo` | Backend | Large-plugin shape: page-route sub-pages + helper module + static | multi-template · page routes · static assets |
| `corp_tools` | Backend | Enterprise-intranet kit: health probes, permission-filtered nav, notice board, i18n, mobile templates | scheduled probes · capabilities · i18n · mobile templates |
| `root_demo` | Backend | Root domain (`framework:core`): read/write core config, audited | root · framework:core · audit |
| `dashboard_demo` | Frontend tool | Admin panel calling backend APIs, ECharts, static assets | frontend tool · admin · ECharts |

See [examples/README.md](examples/README.md).

## Documentation

Detailed specs live in the [Flask Plugin Framework Development Guide](documents/Flask-Plugin-Framework-Dev-Guide-v4.md) (plugin development, permission model, frontend-tool spec, plugin-package format, security design, ops tools):

- [Official examples guide](examples/README.md)
- [Version history & evolution](documents/Flask-Plugin-Framework-Changelog.md)
- [Flask Plugin Framework Roadmap](documents/Flask-Plugin-Framework-Roadmap-v4.md)
- [Version wrap-up checklist](documents/Release-Wrapup-Checklist.md)
- [GitHub Actions setup & open-source publishing guide](documents/GitHub-Actions-Guide.md)
- [Enterprise Edition handover & roadmap (v5.x)](documents/Enterprise-Edition-Handover-Roadmap.md)

## Tests & CI

`tests/` contains **44 scripts** of regression tests (isolated-directory mode, no pollution of project files); GitHub Actions runs them automatically on Python 3.10 / 3.11 / 3.12, covering permissions, plugin-package / frontend-tool chains, integrity signatures, uninstall manifests, Factory Reset, large-plugin multi-template page routing, file transfer (upload limits / Chinese-name downloads / Range), static security scanning, capability cross-validation, runtime audit hooks, i18n framework, plugin data quota, event bus & dependency resolution, device detection & mobile template dispatch, plugin scaffolding / offline install-uninstall CLI, per-plugin space cleanup, ops tools, etc.

<details>
<summary>Expand: 44 test scripts</summary>

```bash
cd FlaskToolkit
python tests/test_permission.py            # permission system 20 assertions
python tests/test_stage2.py                # security hardening regression 19
python tests/test_zip_slip.py              # plugin-package zip slip 19
python tests/test_pack_meta.py             # plugin-package meta consistency 23
python tests/test_reload_race.py           # hot-reload race 1 (20 rounds)
python tests/test_meta_e2e.py              # plugin-package meta end-to-end 11
python tests/test_frontend_zip_slip.py     # frontend-tool zip slip 21
python tests/test_frontend_chain.py        # frontend-tool chain end-to-end 23
python tests/test_admin_api.py             # admin API 69
python tests/test_factory_reset.py         # Factory Reset scope 39
python tests/test_error_pages.py           # error-code pages 12
python tests/test_package_sign.py          # integrity verification / signing 25
python tests/test_plugin_cleanup.py        # uninstall installed_files manifest 23
python tests/test_frontend_permission.py   # frontend-tool access control 25
python tests/test_tools_ops.py             # ops tools backup/reset/config 19
python tests/test_page_router.py           # large-plugin multi-template page routing + pure-API no-name plugin debug page regression 21
python tests/test_framework_fixes.py       # framework small fixes: public_page exemption + CSRF single-injection 12
python tests/test_file_transfer.py         # file transfer: global 413 / plugin & route upload limits / Chinese-name downloads / download stats / Range / on_ready order 12
python tests/test_security.py              # system security: headers / cookie hardening / idle timeout / login lockout & manual unlock 45
python tests/test_plugin_scan.py           # plugin static scanning (v4.3.1): risky imports/calls/obfuscation/network+file touchpoints 35
python tests/test_capabilities.py          # plugin capability declarations (v4.3.2): parse/match/cross-check/runtime authorization 70
python tests/test_root_domain.py            # Root domain & marketplace groundwork (v4.15): framework tiers / plugin-admin service layer / per-plugin update feed 18
python tests/test_framework_manifest.py     # framework directory manifest (v4.15.1): single-source core/user-data lists + Root-domain path check 54
python tests/test_root_demo.py              # example plugin root_demo (v4.15.1): framework:core Root read/write + contrast rejection 19
python tests/test_audit_hook.py            # runtime audit hooks (v4.4.0): event mapping/stack attribution/observe/enforce 38
python tests/test_update_checker.py     # update checker (v4.8.0): version compare / feed cache TTL / archive verify chain / zip-slip guard / update-feed signature verify 50
python tests/test_plugin_updates.py    # plugin update-feed signing (v4.15/v4.17.1): signed verified / tampered·unsigned rejected 8
python tests/test_release_sign.py      # release --sign → update_checker verify chain (v4.17.1) 5
python tests/test_src_layout.py        # package.py src-layout auto-mapping (v4.17.2): <name>.json+frontend/ → plugin.json+templates/static 16
python tests/test_i18n.py                  # i18n (v4.9.0): language packs / lookup chain / lang resolution / cookie switch / template render 29
python tests/test_data_limit.py            # plugin data quota (v4.9.0-4.9.2): path judge / usage / storage:limit declaration / write-dir scope / upload pre-check / global total / TTL / disable 32
python tests/test_setup.py               # first-run wizard + forced password change (v4.10 M4) 17
python tests/test_register.py             # invite-code self-registration + review (v4.10 M5) 25
python tests/test_scaffold_tools.py       # scaffolding + offline install/uninstall (v4.10 M6) 53
python tests/test_network.py              # network & access (v4.11) + 308 redirect / Secure cookie (v4.12) 41
python tests/test_mdns.py                 # mDNS service registration (v4.11, optional zeroconf) 22
python tests/test_ip_watcher.py           # IP-change detection (v4.11) 15
python tests/test_desktop_launcher.py     # desktop launcher (v4.11) + HTTPS checkbox (v4.12) 36
python tests/test_stats.py                  # statistics insight (v4.14): time-bucket + access-profile dual model / dashboard / trend & error top 55
python tests/test_selfcheck.py              # startup self-check (v4.15): CORE_FILES completeness / timezone probe / full check 14
python tests/test_events.py                 # event bus (v4.16): priority / once / off / weakref cleanup / bound-method strong ref / async non-blocking / exception isolation / built-in emission 11
python tests/test_dependency.py             # dependency resolution (v4.16): dep-spec parse / semver incl pre-release / Kahn topo / cycles / missing exclusion 11
python tests/test_plugin_events.py          # BasePlugin event integration + example demos (v4.16): scheduler_demo events & manual trigger / dependent_demo cross-plugin subscription 28
python tests/test_device.py                 # device detection + mobile template dispatch (v4.17): UA classification / config switches / resolve_template / public-page mobile template / BasePlugin mobile namespace 20
# total: 44 scripts
```

</details>

## Edition Status

- **Community Edition (v4.x)**: feature development continues with a deliberately controlled architectural scale, focused on small-LAN / personal-use scenarios; we maintain and release regularly (43-script regression suite + CI).
- **Enterprise Edition (v5.x)**: planned to carry the long-term roadmap (refined permission model, process-level sandboxing, stricter CSP, enterprise identity integration, etc.). Due to limited team capacity, we are openly looking for maintainers to take over — see the [Enterprise Edition handover & roadmap](documents/Enterprise-Edition-Handover-Roadmap.md).

## Known Limitations

- **Security model is "install a plugin = trust its author"**: plugins run in-process with the framework, without sandboxing, and can reach the framework's full filesystem/network surface; only install plugins from trusted sources. Static scanning / capability declarations / runtime audit hooks are **risk-mitigation tools, not absolute isolation** (see dev guide 10.1).
- With that defense in depth, the recommended use is: **local machine or a trusted LAN / enterprise intranet** (pair with the `auth` plugin; optionally enable `PLUGIN_SCAN_MODE=enforce` and `AUDIT_HOOK_MODE=enforce`; for HTTPS see `tools/gen_cert.py`).
- Not hardened for adversarial public networks — **not recommended for direct public exposure**; if you must, put a gateway/reverse-proxy in front and assess the risk yourself.
- For LAN use, set `FLASKTOOLKIT_HOST=0.0.0.0`, pair it with the `auth` plugin, and assess the risk yourself.

## License & Contributing

MIT License · contribution guidelines in [CONTRIBUTING.md](CONTRIBUTING.md) · AI-assisted development was used; see the statement below.

### AI-Assisted Development Statement

This project used AI-assisted programming tools during development, including but not limited to: code generation and refactoring, code review, test case authoring, and documentation writing. All AI-assisted content has been manually reviewed by the developer and is only merged after passing the project's own regression suite (`tests/`, 44 scripts / 1161 assertions) and startup integrity self-check.

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
