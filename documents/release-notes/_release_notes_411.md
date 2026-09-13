## What's New in v4.11.0 — Reachability

This release tackles the pain of *re-publishing your access link every time your IP changes*, and makes the framework reachable for ordinary users — following up on v4.10 (Accessibility: "you can use it") with Reachability: "you can reach it".

### 1. Address Center (`core/network.py`)
Pure-stdlib network utilities: LAN address discovery (`getaddrinfo` + `ipconfig`/`hostname -I` + UDP fallback, filtering `127.*`/`169.254.*`/`0.0.0.0` with dedup), effective-port resolution (runtime registered value > `FLASKTOOLKIT_PORT` env > user config > 5000), and combined reachable access URLs (mDNS on top, loopback-only for `127.0.0.1`, all LAN IPs for `0.0.0.0`). `app.py` now registers the real bound port at startup.

### 2. mDNS Service Registration (`core/mdns.py`)
Optional dependency on `zeroconf` — when missing, the framework degrades gracefully with a `pip install zeroconf` hint. When enabled, the service is reachable at a **stable `flasktoolkit.local` name** that never changes with your IP. `ServiceInfo` construction is compatible with both new (`addresses`) and old (`address`) zeroconf APIs.

### 3. Network & Access Page in the Admin UI
New `/admin/network` page: share entry with every reachable address (one-click copy + QR code via bundled qrcodejs, offline-friendly), current network status, LAN-sharing switch, mDNS switch, hostname, IP-change detection interval, and firewall hints. Backed by `GET/POST /api/admin/network` (whitelisted keys, type validation, audit logging; HOST/mDNS changes require restart).

### 4. Startup Banner + IP-Change Detection
The startup banner now prints all reachable addresses (`[共享] 访问地址...`), so sharing is obvious at a glance. New `core/ip_watcher.py` snapshots your LAN addresses periodically (`IP_WATCH_INTERVAL`, default 30s, 0=off) and logs a warning when your IP changes — no more mystery about who has the old link.

### 5. Desktop Launcher (`tools/desktop_launcher.py`)
A double-click-friendly **tkinter GUI** for users who just want to use the framework: start/stop the server, pick local-only vs LAN-sharing, copy your access address, open the browser, watch the logs. It drives `app.py` via `subprocess` and never imports framework core (no side effects). CLI flags `--smoke` / `--shared` / `--port` for headless/testing use. QR codes appear when `qrcode` + `Pillow` are installed (optional).

### 6. New Config Items
`MDNS_ENABLED` (default off, restart required), `MDNS_HOSTNAME` (default `flasktoolkit`), `IP_WATCH_INTERVAL` (default 30s, 0=off). Also fixed a `release.py bump` bug (it now reads the current version from `global_var.py` as the replacement anchor).

### 7. Docs
README (EN + zh-CN) gained the Reachability highlight and a "no command line?" GUI guide; the development guide gained the v4.11 section with new modules, config-item table and directory tree; Roadmap and version-history records updated.

### 8. Regression
Now **32 scripts / 779 assertions** (up from 28/737), all green: new `test_network` (24), `test_mdns` (22), `test_ip_watcher` (15), `test_desktop_launcher` (27), and `test_admin_api` extended 44→60.

---

**Upgrade hint:** keep your `data/`, `plugins/` (user plugins), `config.json` and custom templates — the runtime package contains the framework code only. `locales/` (built-in language packs), `tools/` (ops CLIs + desktop launcher) and the new `core/network.py`, `core/mdns.py`, `core/ip_watcher.py` are all included.

**Known limits:** mDNS requires LAN multicast support (built into Windows 10+, macOS, most Linux); not reachable across subnets; for public-network exposure please assess your own risks (plugins remain unsandboxed).
