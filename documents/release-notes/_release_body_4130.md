## v4.13.0 — Mobile & Tablet（移动端与平板适配）

A responsive-design overhaul for the framework's frontend pages **and** the admin console, plus all five example plugins — fixing display issues on phones and tablets. Core principle: **the new CSS lives side by side with the original styles** (no original stylesheet was touched), so it is easy to review, tune and revert.

### What's new

- **Public pages — `static/css/mobile.css`**: safe-area insets for notched screens (`viewport-fit=cover` + `env(safe-area-inset)`), ≥44px touch targets, auto-wrapped scrollable tables (`.table-scroll`), a hamburger menu on the home navbar (`.nav-toggle`), 480px / 768px responsive breakpoints.
- **Admin console — `static/css/admin-mobile.css`**: stats grids collapse to a single column, modals go full-screen on narrow screens (`.mobile-full`), toasts become a top banner (`body.mobile-narrow`), plus a mobile nav entry.
- **JS enhancement layer — `static/js/mobile.js`** (IIFE, four pieces, independent from the original JS):
  1. `wrapTables` — automatically wraps every `<table>` in a `.table-scroll` scroll container (skips already-wrapped / nested / in-container tables);
  2. `setupBurger` — injects the ☰ hamburger into the home navbar (tap toggles, tap-outside closes);
  3. `setupModalFull` — modals go full-screen at ≤480px;
  4. `setupToast` — toasts switch to top-banner mode at ≤768px.
  Media-query changes re-apply automatically, and a `MutationObserver` catches tables/modals rendered dynamically by admin JS.
- **Idempotent template injection**: 14 framework templates (incl. `admin/base.html`) gained `viewport-fit=cover` + the mobile `link`/`script` tags; 11 example-plugin templates include their own mobile stylesheet.
- **Example plugins**: all five ship a dedicated mobile stylesheet — `corp_mobile.css`, `demo_mobile.css`, `hello_mobile.css`, `async_mobile.css` and `dashboard_mobile.css`.

### Verification

- Browser end-to-end (home / login / admin dashboard / stats / system pages): resource injection and table-wrapping 100% effective, no JS errors.
- Full regression: **32 scripts / 869 assertions, 0 failures** (Python 3.10–3.12 via CI).

### Upgrade hint

Keep your `data/`, `plugins/` (user plugins), `config.json`, `locales/` and custom templates — the runtime package contains the framework code only. No config change needed.

### Runtime package

- `FlaskToolkit-4.13.0-runtime.zip` (86 files, framework runtime only)
- SHA-256: `a6616e67f56d7ed795be84ae612dd342c949fb81c58e33c173ec3fb3525e8f37`
