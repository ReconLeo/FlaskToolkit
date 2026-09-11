# Security Policy

## Supported Versions

| Version | Support |
|---------|---------|
| **v4.x (Community Edition)** | ✅ Actively maintained — security fixes are backported and land in the next patch or minor release, with the usual full regression (35 scripts / 914 assertions, verified 2026-09-07) + CI |
| **v5.x (Enterprise Edition)** | ⚠️ Roadmap only — carries the long-term enterprise plans (fine-grained permission model, process-level sandbox, stricter CSP, etc.) and is **publicly seeking a new maintainer**. See [Enterprise handover & roadmap](documents/Enterprise-Edition-Handover-Roadmap.md) |
| **< v4.x** | ❌ Not supported — historical versions (archived in `documents/archive/`) receive no security updates |

## Trust Model & Security Posture

Please read this before installing anything:

- **Plugins run in-process with the framework, without sandboxing.** Installing a plugin means trusting its author — this is an explicit design decision (see the development guide, chapter 10). **The `framework:core` permission (v4.15) is the single explicit escalation above that trust model**: a plugin declaring it can read/manage/**modify or delete the framework's own core files** (≈ Linux root). It is surfaced with a loud ⚠️ Root badge in the admin UI and every allowed core-path write is recorded as a **root-access audit event**, but it is shipped under the MIT license — **the framework takes no responsibility for damage caused by high-risk operations**. Only install such plugins from authors you fully trust.
- On top of that "bare trust" model, the framework layers defense in depth:
  1. **AST static scanning** (4.3.1) — blocks obviously risky code at install time;
  2. **Capability declaration & cross-validation** (4.3.2) — a plugin can only exercise what it declares (`filesystem:`, `network:`, `scheduler:`, `storage:` …);
  3. **Runtime audit hooks** (4.4.0) — `sys.addaudithook`-based interception with `off / observe / enforce` modes, per-plugin attribution;
  4. **Data quotas** — per-plugin & global total caps enforced at write time (4.9.0–4.9.2), plus per-plugin storage cleanup from the admin dashboard or the offline CLI (4.10);
  5. **Supply-chain visibility** (4.10) — `pip_dependencies` declared per plugin; missing packages skip that plugin with a `pip install` hint instead of silently installing;
  6. **Transport & access** — optional HTTPS with self-signed cert helper (4.5.0), automatic **HTTP→HTTPS 308 redirect** that keeps POST method & body (4.12), **auto-configured `SESSION_COOKIE_SECURE`** (4.12: on under HTTPS / trusted reverse proxy, off on plain-HTTP LAN), trusted reverse-proxy headers (4.12), login-failure lockout & manual unlock (4.3.0/4.5.1), first-run wizard with **forced password change** (4.10), invite-code self-registration (4.10).
- This posture is designed for **trusted LANs / enterprise intranets** running daily internal tools. Exposing the service to an adversarial public network still requires your own risk assessment — plugins remain unsandboxed.

## Deployment Notes & Attack Surface

When exposing the framework beyond localhost, keep these in mind:

- **LAN sharing is opt-in**: the default bind is `127.0.0.1`. Set `FLASKTOOLKIT_HOST=0.0.0.0` only on a network you trust — combined with the `auth` plugin and, ideally, HTTPS.
- **Reachability features (4.11) widen the surface**: the admin **Network & Access** page and startup banner publish every reachable address (plus share links/QR codes), and optional **mDNS** (`pip install zeroconf`, `MDNS_ENABLED=true`) advertises a stable `flasktoolkit.local` name. Enable these only on trusted LANs; an mDNS-advertised, auth-less instance is trivially discoverable by anyone on the same subnet.
- **Reverse proxy**: enable `TRUST_PROXY_HEADERS` only behind a proxy you control — forged `X-Forwarded-*` headers can bypass client-IP attribution used by login lockout and audit. Set `EXTERNAL_SCHEME=https` so share links/QR codes show the external HTTPS entry (see dev guide 3.4).
- **HTTPS modes (4.12)**: direct HTTPS auto-redirects plain-HTTP port (main+1) with 308 keeping POST; `SESSION_COOKIE_SECURE` auto-adapts (None = automatic). Self-signed certs are for local/trusted-LAN use only — public deployment should use a trusted certificate or proxy TLS termination.
- **Hardening presets**: `python tools/config.py profile strict` applies scan `enforce`, integrity `strict`, stricter lockout (3 tries/30 min) and Secure cookies — intended for HTTPS + trusted intranet deployments.

## Reporting a Vulnerability

**Please do not open a public issue for a security vulnerability.** Report it privately instead:

1. **Preferred — GitHub Security Advisory (private):**
   https://github.com/ReconLeo/FlaskToolkit/security/advisories
2. **Alternative — email:** `reconleo@outlook.com` (PGP-encrypted reports are welcome; key can be requested by reply).

Please include in your report:

- Affected version(s) and the module/file involved (framework core, a built-in plugin, an example, or an ops tool);
- A step-by-step description of how to reproduce (or a minimal PoC);
- The impact you observed (e.g. RCE, data leak, privilege escalation, DoS);
- A suggested fix or mitigation, if you have one.

## What Happens Next

- **Acknowledgement:** within 48 hours.
- **Assessment & fix plan:** typically within 7 days (or a clear rationale why it takes longer / is by design).
- **Disclosure:** fixes land through the normal release cadence with a changelog entry; we do not force a coordinated-disclosure embargo — if you plan to publish, a short heads-up so we can ship a fix first is appreciated.

## Out of Scope

- Vulnerabilities inside **third-party plugins** (including Kaleido/AirDrop sub-projects deployed as plugins) — those are the responsibility of the plugin author; report to them directly.
- Issues in **upstream dependencies** (Flask, APScheduler, watchdog, cryptography, …) — please report to the respective project.
- Already-fixed issues, or issues on **unsupported versions** (< v4.x).
