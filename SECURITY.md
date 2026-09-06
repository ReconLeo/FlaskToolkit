# Security Policy

## Supported Versions

| Version | Support |
|---------|---------|
| **v4.x (Community Edition)** | ✅ Actively maintained — security fixes are backported and land in the next patch or minor release, with the usual full regression (28 scripts / 737 assertions) + CI |
| **v5.x (Enterprise Edition)** | ⚠️ Roadmap only — carries the long-term enterprise plans (fine-grained permission model, process-level sandbox, stricter CSP, etc.) and is **publicly seeking a new maintainer**. See [Enterprise handover & roadmap](documents/Enterprise-Edition-交接与路线.md) |
| **< v4.x** | ❌ Not supported — historical versions (archived in `documents/archive/`) receive no security updates |

## Trust Model & Security Posture

Please read this before installing anything:

- **Plugins run in-process with the framework, without sandboxing.** Installing a plugin means trusting its author — this is an explicit design decision (see the development guide, chapter 10).
- On top of that "bare trust" model, the framework layers defense in depth:
  1. **AST static scanning** (4.3.1) — blocks obviously risky code at install time;
  2. **Capability declaration & cross-validation** (4.3.2) — a plugin can only exercise what it declares (`filesystem:`, `network:`, `scheduler:`, `storage:` …);
  3. **Runtime audit hooks** (4.4.0) — `sys.addaudithook`-based interception with `off / observe / enforce` modes, per-plugin attribution;
  4. Optional **HTTPS** (4.5.0), login-failure lockout & manual unlock (4.3.0/4.5.1), per-plugin & global **data quotas** (4.9.0–4.9.2).
- This posture is designed for **trusted LANs / enterprise intranets** running daily internal tools. Exposing the service to an adversarial public network still requires your own risk assessment — plugins remain unsandboxed.

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
