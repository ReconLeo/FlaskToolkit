## v4.12.2 — Security Fix（上传临时文件防线）

Security hardening for the plugin-upload pipeline, found during the stress & multi-host IP attribution assessment (stages 3–4) and follow-up code audit.

### Security fixes

- **F6 — temp-file cleanup on every failure branch**: previously only plain uploads (and the update endpoint) cleaned up the saved temp package; **preview validation failures and confirm-install failures left `preview_*.zip` files behind**. Repeated failed previews/confirms could fill the temp directory. Now every `except` branch removes the temp file via `_safe_remove_temp()` (best-effort, logs on failure, never blocks the response).
- **Preview-file TTL guard (write-disk protection)**: `_cleanup_stale_preview_files(30 min)` runs at every upload entry — preview packages not confirmed within 30 minutes are swept away, closing the "preview forever, never confirm" accumulation vector.
- **F12 — `preview_id` path traversal (P1)**: validation upgraded from a loose `startswith('preview_')` check to a strict format `^preview_[0-9a-f]{32}\.zip$` (exact uuid-hex match). Requests like `preview_../../evil.zip` are rejected with 400 before touching the filesystem, blocking arbitrary file read/probe.
- **Tests**: `test_admin_api` 62 → 69 assertions (no temp residue after failed plain/preview uploads, forged `preview_id` → 400, traversal → 400, stale preview TTL sweep). Full regression: 32 scripts / 0 failures.

### Housekeeping

- Test residue from the assessment cleaned up: 12 invalid upload zips + the echo-upload test plugin (313 MB of large-file test data).

### Upgrade hint

Keep your `data/`, `plugins/` (user plugins), `config.json`, `locales/` and custom templates — the runtime package contains the framework code only. No config change needed.

### Runtime package

- `FlaskToolkit-4.12.2-runtime.zip` (82 files, framework runtime only)
- SHA-256: `c7af39085faebc7d05444f16724c0c1a1d1c4550f01f58fc58c2217b316eeacd`
