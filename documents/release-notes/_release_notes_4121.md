## v4.12.1 — Secure Fix（登录回归修复）

Hotfix for a P1 regression introduced in v4.12.0, found and verified during the stress & multi-host IP attribution assessment (stages 3–4).

### Fix

- **P1 login regression (F10)**: `SESSION_COOKIE_SECURE` auto mode was globally tied to `EXTERNAL_SCHEME` — with a reverse-proxy deployment (`EXTERNAL_SCHEME=https`), cookies from plain-HTTP direct access (`http://<ip>:<port>`) also got the `Secure` attribute, so browsers/clients discarded them and **every logged-in API call returned 401**. Now `is_secure_cookie_mode()` follows the **actual request scheme** (`request.scheme`, already corrected by ProxyFix behind a proxy): http-direct access gets no `Secure` (login works), https/proxied access keeps it. Explicit `true/false` forcing unchanged. Verified on a real Android device over LAN (direct + Nginx-proxied).

### Assessment delivery (stage 3–4 of the HTTPS stability plan)

- `test_server/` scaffold added: Android test client (probe/stress/upload), PC stress & long-run collectors, audit lookup for IP attribution, and an isolated echo-upload test plugin (removed from runtime).
- **Concurrency**: single-threaded dev server handles 100 concurrent requests error-free (serial queuing, p50 ~2.2s local); dev-server `threaded=True` fails at 100 concurrency (F7 — use single-threaded or a production WSGI like waitress/gunicorn).
- **Large files**: 10/50/100MB uploads verified end-to-end with matching SHA-256 (direct & proxied); route-level `max_upload` breaks the 100MB global cap (F9); remember to raise Nginx `client_max_body_size` accordingly (F11).
- **Multi-host IP attribution (R6 closed)**: audit log records the real Android LAN IP correctly for both direct and proxied topologies (ProxyFix X-Forwarded-For attribution verified on-device).
- Full report: `documents/HTTPS与反向代理稳定性评估-补充-压力与多机归因-2026-09-06.md`.

### Upgrade hint

Keep your `data/`, `plugins/` (user plugins), `config.json`, `locales/` and custom templates — the runtime package contains the framework code only. No config change needed: `SESSION_COOKIE_SECURE` auto mode now follows the actual request protocol, so both http-direct and https-proxied deployments are correct out of the box.

### Runtime package

- `FlaskToolkit-4.12.1-runtime.zip` (82 files, framework runtime only)
- SHA-256: `e855d1730a7c771317687c555b550211cdbcfca331992eb0f183e86d7f9f8098`
