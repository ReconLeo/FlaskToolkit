## v4.12.0 — Secure（安全传输）

The transport-security release: the framework now completes the HTTPS story end-to-end — automatic HTTP→HTTPS redirect, auto-configured Secure cookies, and full reverse-proxy support (Nginx TLS termination), with `config.py` and the desktop launcher adapted accordingly.

### What's New

- **HTTP→HTTPS auto redirect**: with self-signed HTTPS mode on, the framework starts a plain-HTTP entry port (main port + 1) that 308-redirects every request to the HTTPS address — method & body preserved for POST, IPv6-friendly Host parsing, stale `http://` links never die.
- **SESSION_COOKIE_SECURE auto-config**: default is now auto (`None`) — turned on automatically under HTTPS (direct or reverse-proxied) and off on plain-HTTP LAN so browsers don't drop cookies; `true`/`false` still force the value explicitly. Both `token` and `csrf_token` cookies honor it.
- **config.py adapted**: SSL cert/key pairing hints on `set`, plus a new HTTPS status block in `check` (cert pairing / file existence / reverse-proxy consistency).
- **Desktop launcher adapted**: HTTPS checkbox in the GUI + `--https` CLI flag, self-signed certs auto-generated into `data/certs/`.
- **Reverse-proxy support (from the HTTPS stability assessment, stages 1–2)**: `TRUST_PROXY_HEADERS` (Werkzeug ProxyFix for X-Forwarded-Proto/For/Host), `EXTERNAL_SCHEME` / `EXTERNAL_HOST` / `EXTERNAL_PORT` (external scheme/domain/port for share links, QR codes and banners), `validate_ssl_cert` startup check, mDNS hints follow the effective scheme.
- Regression suite: **32 scripts / 807 assertions** (+16: HTTP→HTTPS redirect & Secure-cookie logic, desktop-launcher HTTPS paths).

### Upgrade hint

Keep your `data/`, `plugins/` (user plugins), `config.json`, `locales/` and custom templates — the runtime package contains the framework code only. After upgrading, `SESSION_COOKIE_SECURE` becomes auto by default: under HTTPS / reverse proxy it enables itself; no manual step needed unless you want to force it.

### Runtime package

- `FlaskToolkit-4.12.0-runtime.zip` (83 files, framework runtime only)
- SHA-256: `da9711c16dca1231ea6f6362611d5db326cabf7ea09eeb94b2ba8825eb65ee00`
