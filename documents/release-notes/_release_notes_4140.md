## v4.14.0 — Statistics（数据统计洞察）

Re-planning of the admin **statistics panel**, driven by one question: *"what does the admin console actually need?"* — answered with a four-question frame (how is it going / who is using what / what went wrong / what should I do). The old cumulative counters are upgraded into a **two-dimensional data model: time buckets + access profiles**.

### What's new

- **Data model — `core/stats.py` rewritten**:
  - `daily_stats` time buckets — per-day aggregation of `count / ok / 4xx / 5xx / ms` per `plugin:path` / `frontend:<tool>` (keys consistent with `call_stats`, daily keys use the real request path so the error Top list pinpoints actual endpoints);
  - `access_profile` — dual-dimension visitor profiles: **by_ip** (the traceability primary key: count / last-seen / device classes / linked user) + **by_user** (logged-in identities, **including the admin themselves**; guests are only recorded by IP), plus a `summary` (total visits / first-seen / last-seen);
  - **30-day TTL** cleanup (configurable via `STATS_RETENTION_DAYS`, minimum 7).
- **Instrumentation — `routes/interceptor.py`**: `before_request` stamps `_ft_stats_t0`, a new `after_request` hook (`global_stats_recorder`) writes buckets + profiles for `/api/<plugin>/` (excl. `/api/admin/`) and `/frontend/<tool>`, and profiles-only for `/plugin/` pages. **Clear responsibility split prevents double counting** — cumulative counters stay with the original hooks. Unauthorized (401/403) and 404 requests land in the 4xx bucket.
- **Device classification**: `classify_device` — pure UA keyword matching (`bot / tablet / mobile / desktop`), zero new dependencies.
- **Dashboard becomes an overview** — runtime badge row (uptime / scheme / address count / IP-change status), **cold-plugin hints** (installed & enabled but never called, with quick links), a **recent-activity card** (audit stream, last 8 entries); the previously-missing **Network & Access** page entry is added.
- **Stats page** — **14-day request trend** (pure-SVG bar chart, no JS dependencies), **error Top table** (TOP-20 4xx/5xx endpoints), **access-profile cards** (user Top-10 / IP Top-10 / device distribution bars). API: `/api/admin/stats` extended with `daily_series / error_top / access_profile / cold_plugins / stats_retention_days`; `/api/admin/system/info` adds `uptime_seconds`.
- **Config**: `STATS_RETENTION_DAYS` (int, default 30, min 7) + `ACCESS_PROFILE_ENABLED` (bool, default true) in `CONFIG_ITEMS`; Factory Reset's `stats_logs` scope now clears the new domains too.

### Framework bug fixed (exposed by test J3)

`start_http_redirect`'s `_jump` never consumed the request body — under the single-threaded `HTTPServer`, a POST/PUT with a body could get **RST'd mid-send (WinError 10053)**, causing intermittent connection aborts on the plain-HTTP redirect port in real deployments. Fixed by draining `Content-Length` bytes before answering.

### Verification

- New `tests/test_stats.py` (55 assertions: device classification / bucket aggregation / profiles / TTL cleanup / trend series / error Top / switch-off / legacy-API compatibility); `test_audit_hook` E12 switched to an audit-log *trace* check (a real `data/audit.log` always exists while the framework runs).
- Full regression: **33 scripts / 869 assertions, 0 failures**.

### Upgrade hint

Keep your `data/`, `plugins/` (user plugins), `config.json`, `locales/` and custom templates — the runtime package contains the framework code only. New stats domains (`daily_stats` / `access_profile`) initialize on first write; no config change needed.

### Runtime package

- `FlaskToolkit-4.14.0-runtime.zip` (86 files, framework runtime only)
- SHA-256: `9de19bf2a623b28db0caea1c69c1c32a8c5664931678e8cbf80828e514c97909`
