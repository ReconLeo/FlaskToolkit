# FlaskToolkit

<p align="center">
  <img src="https://github.com/ReconLeo/FlaskToolkit/actions/workflows/ci.yml/badge.svg" alt="CI">
  <img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
  <img src="https://img.shields.io/badge/version-4.2.0-blue" alt="Version">
</p>

> A Flask-based plugin **framework**: bring scattered Python plugins and pure-frontend tools into one unified runtime —
> dynamically installable, hot-reloadable, permission-controlled. Self-written, self-maintained, runs only on your own machine.

> **English**: this page · **中文**：[中文](README.zh-CN.md)

## Why FlaskToolkit (Author's Story)

I have written a lot of "little things": sign-in scripts, scheduled tasks, file handlers, chart pages… Most are in Python, many are Flask pages with the frontend and backend in one, and quite a few are pure-frontend HTML. Each works well on its own, but they are scattered across folders — every time I wanted to add a feature, I had to reinvent login/auth, upload/download, page skeletons, and scheduled jobs from scratch.

What bothered me even more: more and more things that should stay lightweight were being pushed online — unusable offline, and quietly collecting my data. I did not want to register an account and accept a privacy policy just to use an internal mini tool. What I wanted were small programs running on my own computer (at most shared with a few people on a LAN).

So FlaskToolkit was born: a plugin **framework** — not another run-of-the-mill tools site — that packs my "private little apps", along with their capabilities, into one reusable and extensible foundation.

Over time it grew into what it is today:

- From single-file plugins grew **plugin packages (.zip)** — plugins ship together with their templates and static assets, install and go;
- Pure-frontend HTML tools can also be installed as **first-class citizens**, on equal footing with Python plugins;
- Large plugins can be split cleanly — **multi-template + helper modules + static assets**; one plugin can have its own sub-pages, utility modules, and style/script files (page routes with `page=True`);
- Unified three-level permissions, optional auth, audit logs, hot reload — save a page and it takes effect, no restart needed;
- Added plugin-package integrity verification & signing, Factory Reset, backup/restore, startup self-check, plus a **310-assertion regression suite and GitHub Actions CI**.

To be honest, this framework is far from "production-grade". It is more of a "play for fun" project: standing on the shoulders of giants like Flask, APScheduler, and Werkzeug, and landing the parts I needed. That is also why its security model is bluntly simple — **installing a plugin means trusting its author**. It suits your own machine or a trusted LAN, not a public production environment.

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
python examples/install_all.py                            # install all 6 official examples
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
| `dashboard_demo` | Frontend tool | Admin permission, calls backend APIs, ECharts, static assets |

See [examples/README.md](examples/README.md).

## Documentation

Detailed specs live in the [Flask Plugin Framework Development Guide](documents/Flask插件框架开发规范-v4.0.md) (plugin development, permission model, frontend-tool spec, plugin-package format, security design, ops tools):

- [Official examples guide](examples/README.md)
- [Flask Plugin Framework Roadmap](documents/Flask插件框架-Roadmap-v4.1.md)
- [GitHub Actions setup & open-source publishing guide](documents/GitHub-Actions-上手与开源发布指南.md)

## Tests & CI

`tests/` contains **16 scripts / 310 assertions** of regression tests (isolated-directory mode, no pollution of project files); GitHub Actions runs them automatically on Python 3.10 / 3.11 / 3.12, covering permissions, plugin-package / frontend-tool chains, integrity signatures, uninstall manifests, Factory Reset, large-plugin multi-template page routing, ops tools, etc.

<details>
<summary>Expand: 16 test scripts</summary>

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
python tests/test_admin_api.py             # admin API 21
python tests/test_factory_reset.py         # Factory Reset scope 37
python tests/test_error_pages.py           # error-code pages 12
python tests/test_package_sign.py          # integrity verification / signing 22
python tests/test_plugin_cleanup.py        # uninstall installed_files manifest 23
python tests/test_frontend_permission.py   # frontend-tool access control 25
python tests/test_tools_ops.py             # ops tools backup/reset/config 19
python tests/test_page_router.py           # large-plugin multi-template page routing + pure-API no-name plugin debug page regression 21
# total: 16 scripts / 310 assertions
```

</details>

## Known Limitations

- **Security model is "install a plugin = trust its author"**: plugins can execute arbitrary code; only install plugins from trusted sources.
- The framework leans toward "play for fun" utilities and is not hardened for adversarial public networks — **not recommended for public-facing production deployment**.
- For LAN use, set `FLASKTOOLKIT_HOST=0.0.0.0`, but pair it with the `auth` plugin and assess the risk yourself.

## License & Contributing

MIT License · contribution guidelines in [CONTRIBUTING.md](CONTRIBUTING.md) · AI-assisted development was used; see the statement below.

### AI-Assisted Development Statement

This project used AI-assisted programming tools during development, including but not limited to: code generation and refactoring, code review, test case authoring, and documentation writing. All AI-assisted content has been manually reviewed by the developer and is only merged after passing the project's own regression suite (`tests/`, 310 assertions) and startup integrity self-check.

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
