# FlaskToolkit Plugin Development — Getting Started

> **A hands-on, from-zero-to-release tutorial for building your first plugin.**
>
> The companion tutorial to the [Development Guide](Flask-Plugin-Framework-Dev-Guide-v4.md).
> The Dev Guide is the authoritative *reference* (organized by capability). This
> tutorial is the *path* — it walks a real plugin from a bare Flask file to a
> signed, released package, so you learn the natural flow of plugin development
> rather than a list of features.
>
> **Who this is for** · First-time plugin developers who want a working plugin on
> screen in a couple of hours.
> **What you will build** · Your own plugin, guided by the real-world **AirDrop**
> (a LAN file-share tool) that was pluginized exactly this way.
> **Prerequisites** · Python 3.10+, a recent FlaskToolkit runtime, basic Flask & Python.

---

## Before you start: how this tutorial works

> **Scope note — backend plugin packages only.** This tutorial covers **backend plugin
> packages** (the `.py`-based plugins). FlaskToolkit also ships **frontend tool packages**
> — a `config.json` + static HTML/CSS/JS (see `examples/frontend_tools/dashboard_demo`) —
> which are simpler and self-contained. Those are **not** covered here; see the Dev Guide's
> frontend-tools section.

Every part follows the same rhythm:

```
Goal → Steps (with real code) → Verify (how to confirm it works) → Pitfalls → Dev-Guide ref
```

Throughout the tutorial we follow **AirDrop** — a plugin that started as a single-file
Flask app (`simple-airdrop.py`, 532 lines, 10 routes) and was migrated step by step
into a signed, theme-aware, strictly-compliant plugin. Every fragment is real code
from that journey, so the pitfalls you meet are the ones that actually happened.

| Part | What you learn |
|------|----------------|
| 0 | What a plugin is |
| 1 | Environment & first run |
| 2 | Your first plugin skeleton |
| 3 | Pages & frontend assets |
| 4 | APIs, data & file transfer |
| 5 | Auth & permissions |
| 6 | Capabilities & strict mode |
| 7 | Packaging & distribution |
| 8 | Iteration & release |
| 9 | Advanced: theme, i18n, mobile & feedback loop |

---

## Part 0 — What a plugin is

A FlaskToolkit plugin is a **self-contained capability unit** that the framework
loads, governs and serves. Concretely it is a folder with at most these pieces:

```
my_plugin/
├── plugin.json               # manifest: identity, version, capabilities
├── my_plugin.py              # the Python class, subclass of BasePlugin
├── templates/                # (optional) Jinja templates
│   └── my_plugin/            #   namespace: templates/plugins/<name>/ at runtime
│       └── index.html
├── static/                   # (optional) CSS/JS/images
│   └── ...
└── locales/                  # (optional) i18n strings
```

The runtime layout matters, not the source layout. When installed, the framework maps
`templates/*` → `templates/plugins/<name>/*` and `static/*` →
`templates/plugins/static/<name>/*`.

> **Multiple `.py` files are allowed**, but exactly one must be named `<name>.py` matching
> your plugin's `name` — the framework imports *that* file as the plugin entry point. Other
> modules (e.g. `multitool_utils.py` in `multitool_demo`) are plain helper modules you import
> yourself (`from plugins import multitool_utils`). Templates/static still live under the
> `<name>` namespace regardless of how many `.py` files you have.

Three things make a plugin *a plugin*:

1. **`plugin.json`** — the manifest the framework trusts. Fields must match the Python
   class attributes exactly (see Pitfalls below).
2. **A class subclassing `BasePlugin`** — with `name`, `version`, `title`, etc.
3. **Lifecycle hooks** — `on_load()` (after load), `on_ready()` (after all plugins
   load; used for strict cross-plugin checks), `on_shutdown()`, `on_unload()`.

```python
from plugins.base_plugin import BasePlugin

class MyPlugin(BasePlugin):
    name = "my_plugin"
    title = "My Plugin"
    description = "Does something useful."
    version = "1.0.0"
    author = "You"
    category = "工具"
    permission = "user"
    require_framework_version = "4.19.1"

    def on_load(self):
        self.logger.info("my_plugin loaded")
```

> **Dev-Guide ref** — BasePlugin reference (class attrs & lifecycle) in §3.2, plugin
> pack structure in §6.1.

**Pitfall — manifest/class drift.** `plugin.json` and the class attributes must stay
in sync (`name`, `version`, `title`, `description`, `permission`,
`require_framework_version`, `capabilities`). If they disagree, installation is
rejected with a message listing the offending fields and *both* values (v4.17.2+).
Always bump them together.

---

## Part 1 — Environment & first run

Get a clean runtime so the framework, not your machine, defines the baseline.

1. **Download a release runtime** (cleaner than a dev checkout):

   ```bash
   gh release download v4.19.1 --repo ReconLeo/FlaskToolkit --pattern "FlaskToolkit-4.19.1-runtime.zip"
   unzip FlaskToolkit-4.19.1-runtime.zip -d ftk
   cd ftk
   ```

   Verify it (sha256 is listed in the release notes) and that it boots:

   ```bash
   python app.py          # → "完整性自检通过" + "服务启动地址: http://127.0.0.1:5000"
   ```

2. **Know the layout** (relevant parts):

   ```
   ftk/
   ├── plugins/                # plugins live here (my_plugin.py + my_plugin.json)
   │   ├── base_plugin.py      # the BasePlugin you subclass
   │   ├── auth.py             # optional auth plugin
   ├── templates/plugins/      # plugin templates namespace
   ├── tools/                  # package.py / install_plugin.py / scan.py / config.py
   ├── core/                   # framework services (theme, quota, network, ...)
   ├── static/                 # framework CSS/JS (theme.css, theme.js, plugin_common.js)
   └── global_var.py           # framework version & config
   ```

3. **Load a plugin two ways** (we use both in this tutorial):
   - **Source deploy** — drop `my_plugin.py` + `my_plugin.json` into `plugins/` (fast, for iterating).
   - **Package install** — `python tools/install_plugin.py backend my_plugin.zip` (the distribution path).

> **Dev-Guide ref** — runtime layout & tools in §2; startup self-check in §2.2.

**Pitfall — data-dir write probe on sandboxes.** If `data/` is unwritable, self-check
warns but the server still boots. For local dev this is irrelevant.

---

## Part 2 — Your first plugin

The goal of this part: get a trivial plugin loading and its page rendering.

### 2.1 The skeleton

AirDrop's first usable skeleton was just a manifest + class. Copy this shape:

`plugin.json`
```json
{
  "name": "my_plugin",
  "title": "My Plugin",
  "version": "1.0.0",
  "author": "You",
  "category": "工具",
  "description": "Does something useful.",
  "permission": "user",
  "require_framework_version": "4.19.1",
  "capabilities": []
}
```

`my_plugin.py`
```python
from plugins.base_plugin import BasePlugin

class MyPlugin(BasePlugin):
    name = "my_plugin"
    title = "My Plugin"
    description = "Does something useful."
    version = "1.0.0"
    author = "You"
    category = "工具"
    permission = "user"
    require_framework_version = "4.19.1"
```

> **JSON is strict — no comments!** AirDrop's first `airdrop.json` used trailing `#`
> comments and was silently ignored (the plugin fell back to class defaults, losing
> its `capabilities`). If your plugin behaves oddly in strict mode, check the manifest
> is valid JSON. From v4.17.2 the framework marks such a plugin "描述文件失效"
> (description file invalid) in the admin plugin list.

### 2.2 The route map

A plugin exposes three URL spaces (this is the mental model that makes everything else
click):

| URL | Purpose |
|-----|---------|
| `/plugin/<name>` | the main **page** (HTML) |
| `/plugin/<name>/<sub>` | sub-pages (large multi-page plugins) |
| `/api/<name>/<path>` | **JSON APIs** (your data endpoints) |

Declare routes with the `@permission` decorator for auth, and a plain `path` for
sub-pages (see Part 4 & 5). A minimal route set, with an `echo` API you can curl right
after boot:

```python
# in __init__, or set self.routes on the instance
self.routes = [
    {"path": "/echo", "methods": ["GET"], "view_func": self.echo, "permission": "public"},
]

@permission_required("public")
def echo(self):
    return {"echo": request.args.get("q", "")}   # dict → auto JSON (API dispatcher)
```

```bash
curl "http://127.0.0.1:5000/api/my_plugin/echo?q=hi"   # {"echo": "hi"}
```

### 2.3 Verify

```bash
python tools/scan.py plugins/my_plugin.py     # static scan: high=0, no undeclared behavior
python app.py                                  # boot; check log for "my_plugin loaded"
curl http://127.0.0.1:5000/plugin/my_plugin    # 200 — even a bare plugin renders a page
#   (no custom template? the framework falls back to plugin_default.html, an API-debug
#    page that lists your routes — so /plugin/<name> is never 404)
curl http://127.0.0.1:5000/api/my_plugin/echo  # your first API (from the route above)
```

> **Dev-Guide ref** — plugin.json fields in §6.1.1; URL spaces in §4.

**Pitfall — scan before you declare.** Run `scan.py` early. In **strict (enforce) mode**
a plugin is *rejected* if it has `high`-risk calls (e.g. `subprocess`, raw `socket`)
unless they are justified — merely listing `capabilities` does **not** exempt a `high`
risk (see Part 6). And note the AST scan cannot be bypassed by declaring a matching
`capabilities` entry — the sanctioned way to clear a `high` risk is **refactoring to a
framework service** (Part 6.3), not working around the scanner.

---

## Part 3 — Pages & frontend assets

Now give your plugin a real page. AirDrop's page is a self-contained HTML file with an
inline `<style>` and a QR library.

### 3.1 Template namespace

At runtime your page template lives at `templates/plugins/<name>/`. The framework
resolves `plugins/<name>/<template>` when you render. AirDrop's is
`templates/plugins/airdrop/index.html`, rendered with:

```python
# in the plugin class
def page_index(self):
    return self.render("index.html", files=self.list_files())
```

`index.html` is a normal Jinja template; the `files` argument is passed through and
rendered on the server:

```html
<!-- templates/my_plugin/index.html -->
<!DOCTYPE html>
<html lang="zh-CN">
<head><title>My Plugin</title></head>
<body>
  <h1>My Plugin</h1>
  <ul>
    {% for f in files %}
      <li>{{ f.name }} · {{ f.size }}</li>
    {% else %}
      <li>No files yet</li>
    {% endfor %}
  </ul>
</body>
</html>
```

(For large plugins, declare sub-pages with `page=True` routes; see Dev-Guide §4.5.)

### 3.2 Static assets

Plugin static files are served from `templates/plugins/static/<name>/` and referenced as:

```html
<link rel="stylesheet" href="/plugin-static/my_plugin/style.css">
<script src="/plugin-static/my_plugin/app.js"></script>
```

### 3.3 Frontend auth with plugin_common.js

The framework ships `static/js/plugin_common.js` which centralizes auth handling.
Load it and call APIs through `PluginCommon.request()`:

```html
<script src="/static/js/plugin_common.js"></script>
<script>
  PluginCommon.request('/api/airdrop/files', { method: 'GET' })
    .then(r => { /* render file list */ });
</script>
```

`plugin_common.js` injects CSRF tokens once, handles 401 redirects and provides the
`PluginCommon` helper object — you do **not** hand-write token headers.

> **Pitfall — double CSRF.** Older plugins that manually added `X-CSRF-Token` *and*
> used `PluginCommon.request()` got the header injected twice; the browser joins them
> into `token, token` and CSRF validation fails (403). `plugin_common.js` already
> injects it — don't add it yourself.

### 3.4 Verify

```bash
curl -s http://127.0.0.1:5000/plugin/airdrop | head        # 200, your HTML
curl -s -I http://127.0.0.1:5000/plugin-static/airdrop/qrcode.min.js   # 200
```

> **Dev-Guide ref** — templates & static in §6.3; plugin_common.js in §8.

**Pitfall — public-page login guard.** By default `/plugin/*` requires login. If your
plugin is a *public* tool (no login needed), set `public_page = True` on the class and
the framework's interceptor will exempt that plugin's *page*. It is a class attribute, so
set it directly (or flip it dynamically when your auth mode changes):

```python
class MyPlugin(BasePlugin):
    public_page = True   # /plugin/my_plugin needs no login

# or, for a config-driven dual-mode (AirDrop):
def _apply_auth_mode(self):
    self.public_page = not self.config.get("auth_required", False)
    if self.config.get("auth_required", False):
        for r in self.routes:              # enforce the permission matrix
            r["permission"] = r.get("_real_permission", "user")
    else:
        for r in self.routes:              # downgrade everything to public
            r["permission"] = "public"
```

Remember: `public_page` exempts the **page**; the **API routes** still need their own
`permission` (AirDrop sets both — see Part 5).

---

## Part 4 — APIs, data & file transfer

Your plugin's real work happens behind `/api/<name>/...`. This part covers the
common patterns AirDrop needed: file listing, upload, download, delete.

### 4.1 Declaring API routes

Register routes in `__init__` or via the routes list. AirDrop's upload uses the
framework's **sync upload helper** `save_uploads` (v4.18+) — no hand-rolled
sanitize/quota/save loop:

```python
def upload_files(self):
    # getlist multi-file, sanitize filename, dedup, per-file size + storage-quota
    # pre-checks, save directly to uploads dir — all in one call.
    results = self.save_uploads('files')     # defaults to self.upload_dir
    saved = [r for r in results if r['status'] == 'saved']
    return self.jsonify_ok({"files": saved})
```

Behind the scenes `save_uploads` does what every file-share plugin needs:
single/multi-file `getlist`, filename sanitization (path-traversal-safe), auto-renaming
on name collisions, per-file size check **and** storage-quota check, then `file.save`
to the persistent dir. Returns a list of per-file results with partial-success
semantics.

### 4.2 Sending a file back

```python
def download(self, filename):
    safe = self.sanitize_filename(filename)
    path = os.path.join(self.upload_dir, safe)
    if not os.path.isfile(path):
        return self.jsonify_error("文件不存在")
    # RFC 5987 filename + download logging handled by the framework:
    return self.send_file_response(file_path=path, as_attachment=True, download_name=safe)
```

### 4.3 Other framework helpers you'll reuse

| Helper | Purpose |
|--------|---------|
| `save_uploads(...)` | sync multi-file upload to a persistent dir (v4.18) |
| `sanitize_filename(name)` | path-traversal-safe filename (v4.18, stricter than `core.utils.secure_filename_cn`) |
| `save_uploaded_file(...)` | **async**-oriented upload → plugin temp dir (for `run_async_task` flows) |
| `send_file_response(...)` | RFC5987 download + download logging |
| `check_upload_limit(...)` | per-file size pre-check |
| `check_upload(size)` | storage-quota pre-check (`storage:limit`) |
| `get_data_path()` | per-plugin data directory (v4.3.2+) |

### 4.4 Verify

```bash
curl -F "files=@hello.txt" http://127.0.0.1:5000/api/my_plugin/upload     # saved
curl http://127.0.0.1:5000/api/my_plugin/files                            # lists hello.txt
curl -OJ http://127.0.0.1:5000/api/my_plugin/download/hello.txt           # downloads
```

> **Dev-Guide ref** — route declaration in §4; file transfer helpers in §5.4; the
> async temp-dir chain (which `save_uploaded_file` belongs to) in §5.4.2.

**Pitfall — choosing upload helper.** Ask "is this **sync** (user uploads, frontend
immediately downloads from the saved file) or **async** (upload to temp, background job
processes, then serve)?" AirDrop is sync → `save_uploads`. The async path needs
`save_uploaded_file` + `run_async_task`. Using the wrong one is the #1 friction AirDrop
hit (see the `save_uploads` design doc).

**When is async used?** Media-processing plugins — e.g. an `ffmpeg` wrapper that
converts an uploaded video — save the upload to the plugin temp dir, run the job in the
background (`run_async_task`), then serve the result. Async is an **advanced** topic and
is not covered in this tutorial; see Dev-Guide §5.4.2 and the `async_file_demo` example.

---

## Part 5 — Auth & permissions

The framework has three permission levels: `public` (guest), `user` (logged in),
`admin`. Gate each API route with the `@permission` decorator:

```python
from plugins.base_plugin import BasePlugin, permission as permission_required

class MyPlugin(BasePlugin):
    def __init__(self, app):
        super().__init__(app)
        self.routes = [
            {"path": "/public",  "methods": ["GET"], "view_func": self.public_info,  "permission": "public"},
            {"path": "/files",   "methods": ["GET"], "view_func": self.list_files,   "permission": "user"},
            {"path": "/delete",  "methods": ["POST"], "view_func": self.delete_file, "permission": "admin"},
        ]

    @permission_required("public")
    def public_info(self): ...
```

### 5.1 Configurable dual-mode auth

> **Plugins carry their own config.** Define defaults (`DEFAULT_CONFIG`) persisted to
> `plugins/configs/<name>.json`, read with `self.load_config()`, save with
> `self.save_config()`, and **editable by admins from the framework's admin backend**. A
> plugin can therefore change its runtime behavior from config — AirDrop's `auth_required`
> is a real example of a config knob that reconfigures its routes at load time.

AirDrop ships a **config switch** `auth_required` in `plugins/configs/airdrop.json`:

- `false` (default) → every route is `public`, the page is `public_page = True`,
  plug-and-play with no login.
- `true` → routes enforce the permission matrix (read=public, upload=user,
  delete/open-folder=admin) and require the framework's `auth` plugin.

```python
def _apply_auth_mode(self):
    if self.config.get("auth_required", False):
        # routes already carry real permission levels
        return
    # downgrade everything to public + expose page without login
    for r in self.routes:
        r["permission"] = "public"
    self.public_page = True
```

### 5.2 Verify

```bash
# auth_required=false
curl http://127.0.0.1:5000/api/my_plugin/upload       # 200, no login
# auth_required=true  (with auth plugin enabled)
curl http://127.0.0.1:5000/api/my_plugin/upload       # 401
curl -H "Cookie: ..." http://127.0.0.1:5000/api/my_plugin/upload   # 200 (user)
```

> **Dev-Guide ref** — permissions & `@permission` in §3.5; the auth plugin in §8.

**Pitfall — page vs API guards differ.** The *page* guard uses `public_page`; the *API*
guard uses per-route `permission`. A public plugin must set **both** (page exemption +
public routes) — AirDrop's `_apply_auth_mode` does exactly that.

---

## Part 6 — Capabilities & strict mode

This is where a *correct* plugin becomes a *trusted* plugin.

### 6.1 Capabilities manifest

Declare what your plugin is allowed to touch in `plugin.json` `capabilities`. AirDrop
declares:

```json
"capabilities": [
  "filesystem:read:uploads",
  "filesystem:write:uploads",
  "storage:limit:10gb",
  "scheduler"
]
```

### 6.2 Why strict mode exists

The framework can run in **strict mode** (`PLUGIN_SCAN_MODE=enforce` +
`PACKAGE_INTEGRITY_MODE=strict` + `AUDIT_HOOK_MODE=enforce`). Under enforce:

- every plugin is statically scanned at install/load;
- a **`high`-risk call** (e.g. `subprocess`, raw `socket`) rejects the plugin
  *unconditionally* — declaring a matching capability does **not** exempt it
  (`capabilities` only resolves `missing` gaps, never a `high` risk);
- undeclared behavior is flagged.

### 6.3 Use framework services instead of raw risky calls

The clean fix is usually "let the framework do it." AirDrop had to:

| Raw call | Framework replacement |
|----------|----------------------|
| `subprocess` to enumerate LAN IPs | `core.network` (address center) |
| raw `socket` for the same | `core.network` |
| `os.startfile` to open folder | kept, gated as `process` (declared) |

After refactoring, `scan.py` reported `high=0`:

```bash
python tools/scan.py plugins/airdrop.py
# → high=0 medium=4 ... 结论: 无高风险行为
#   (medium = os.remove delete-file, covered by filesystem:write:uploads)
```

### 6.4 Storage quota

Declare `storage:limit:10gb` in `capabilities` and the framework enforces a quota on
that directory (used automatically by `save_uploads` / `check_upload`).

### 6.5 Verify

```bash
python tools/scan.py plugins/my_plugin.py     # high=0, no undeclared behavior
python app.py                                  # boots under enforce, plugin loads
```

> **Dev-Guide ref** — capabilities model in §10.7; static scanner in §10.6; strict mode
> in §2.4.

**Pitfall — high risk ≠ capability.** If scan reports a `high` item, don't "fix" it by
adding a capability line. Refactor to use a framework service, or justify keeping it and
ensure the scan gate still passes. This is the single biggest mindset shift when you
turn on strict mode.

---

## Part 7 — Packaging & distribution

Move from source files to a **signed, installable package**.

### 7.1 Package source layout

Assemble a package source folder (AirDrop keeps it in `package/`):

```
package/
├── plugin.json              # manifest
├── my_plugin.py             # main class
├── templates/index.html     # → templates/plugins/<name>/index.html
├── static/                  # → templates/plugins/static/<name>/
└── (locales/ optional)
```

> v4.17.2+ `tools/package.py` also has `--src-layout`, which *attempts* to infer the
> package layout from a dev layout (`<name>.json` + `<name>.py` + `frontend/`). Inference is
> **best-effort, not guaranteed** — always verify the produced zip yourself (Part 7.4) and
> fix the source layout if a file lands in the wrong namespace.

### 7.2 Sign it

Optional but recommended for distribution. Generate a project keypair once:

```bash
python tools/package.py genkey -o keys/private.pem --pub keys/public.pem
```

Pack and sign:

```bash
python tools/package.py pack package/ -o dist/my_plugin-v1.0.0.zip \
    --type backend --sign keys/private.pem --signer "You <you@example.com>"
```

Verify (integrity + signature) and scan the artifact:

```bash
python tools/package.py verify dist/my_plugin-v1.0.0.zip    # 完整性 + 签名有效
python tools/scan.py dist/my_plugin-v1.0.0.zip              # high=0
```

### 7.3 Install

```bash
python tools/install_plugin.py backend dist/my_plugin-v1.0.0.zip    # fresh install
python tools/install_plugin.py backend dist/my_plugin-v1.1.0.zip --update   # upgrade
```

Install runs scan-gate + manifest parse (field consistency) + package verify, then
maps templates/static into the framework namespaces and records an `installed_files`
manifest for clean uninstall.

> **Signing key handling.** Commit the **public** key (`keys/public.pem`) so self-hosts
> can configure `PLUGIN_PUBLIC_KEY_PEM` for real signature verification. **Never commit
> the private key.** A signed package still installs fine when no public key is
> configured — verification is just skipped.

### 7.4 Verify

```bash
# after install
grep -n "version" plugins/my_plugin.py               # 1.0.0
ls templates/plugins/my_plugin/ templates/plugins/static/my_plugin/
```

> **Dev-Guide ref** — packaging & tools in §6; integrity/signature in §10.5.

**Pitfall — keep the class and manifest in sync before packing.** `install_plugin`
rejects a package whose `plugin.json` disagrees with the class (`version`,
`description`, ...). Bump both files together — AirDrop's `description` once drifted
between the two and install refused it.

---

## Part 8 — Iteration & release

A release is: correct version metadata + tag + GitHub Release with the signed zip.

### 8.1 Version rules

- `version` must be identical in **three places**: the class attr, `plugin.json`, and
  `package/plugin.json` (the distribution manifest).
- `require_framework_version` must be **≤ the running framework**, but ≥ whatever new
  framework API you use. Bump it when you adopt a newer feature (e.g. AirDrop used
  `theme_effective` → required **4.19.1**).
- `require_framework_version` too high → install is rejected (you must bump the
  framework or lower the requirement).

### 8.2 Ship

```bash
git add -A && git commit -m "feat(plugin): ... (v1.3.0)"
git tag v1.3.0
git push origin main v1.3.0
gh release create v1.3.0 dist/airdrop-v1.3.0.zip --notes "..."   # attach the signed zip
```

Users then install straight from the release:

```bash
gh release download v1.3.0 --pattern "*.zip" --repo You/your-plugin
python tools/install_plugin.py backend your-plugin-v1.3.0.zip
```

### 8.3 Verify

```bash
gh release view v1.3.0        # asset listed
python tools/package.py verify <downloaded zip>   # integrity + signature
```

> **Dev-Guide ref** — version & release checklist in §9 and `Release-Wrapup-Checklist.md`.

---

## Part 9 — Advanced: theme, i18n, mobile & the feedback loop

Once your plugin runs, make it feel native to the framework's ecosystem.

### 9.1 Dark mode / theme (v4.19.x)

The framework is fully dark-mode capable and exposes a **three-piece hookup** for
self-contained plugins (AirDrop uses exactly this — see its `index.html`):

```html
<!DOCTYPE html>
<html lang="zh-CN" data-theme-init="{{ theme_effective }}" data-themes='{{ available_themes|tojson }}'>
<head>
    <link rel="stylesheet" href="/static/css/theme.css">      <!-- semantic CSS vars -->
    <link rel="stylesheet" href="/plugin-static/my_plugin/style.css"> <!-- your styles -->
    <script src="/static/js/theme.js"></script>               <!-- sets <html data-theme> -->
</head>
...
```

- `theme_effective` is injected into **every template (including plugin pages)** by the
  framework — `light`/`dark` are the effective values, `auto` defers to the browser.
- `theme.css` defines semantic variables (`--bg`, `--card-bg`, `--text`, `--border`,
  `--primary`, ...) plus a `:root[data-theme="dark"]` override set. **Reference these
  variables in your own CSS** and you get dark mode for free — no duplicated palettes.
- `theme.js` reads `<html data-theme-init>`, sets `<html data-theme>`, follows the OS
  via `prefers-color-scheme`, and exposes `window.Theme.switch(code)`.

AirDrop migrated its hard-coded colors to the variables (`#f5f7fa` → `var(--bg)`,
`#2c3e50` → `var(--text)`, `white` → `var(--card-bg)`, ...) and added a small
`[data-theme="dark"]` override block for the few functional colors (drag-over green,
address-chip blue, QR placeholder) that have no variable.

For backend conditional rendering, use `core.theme.resolve_effective_theme()`
(`light`/`dark`/`auto`); for the *real* resolved shade under `auto` (which only the
browser knows), use `window.Theme.current()`.

> **More than light/dark? (v4.19.2)** The theme system is **extensible by dropping in a
> folder** — no code changes. Put a `themes/<name>/{theme.json,theme.css}` directory on
> disk (theme name must match `^[a-zA-Z0-9_-]+$`, `theme.json` carries `name`/`title`,
> `theme.css` is a `[data-theme="<name>"]` semantic-variable override set) and it is
> auto-discovered by scanning `BASE_DIR/themes/`, appears in the theme switcher, and
> loads via `/theme-static/<name>/theme.css`. The release ships a `sepia` example. If a
> custom theme is removed at runtime, the backend falls back to `auto` (keeps the cookie
> so the preference returns if the folder is restored) and the frontend falls back to
> `auto` on a missing CSS. Any plugin referencing the semantic variables (shown above)
> inherits each new theme for free.

> **Dev-Guide ref** — theme in §5.11 (the "插件接入主题" subsection is the canonical
> three-piece recipe).

### 9.2 i18n

Add `locales/<lang>.json`; the framework merges them and exposes a `t` translator and
`lang`/`available_langs` to templates. See Dev-Guide §7.

### 9.3 Mobile

`core/device` detects mobile/tablet and the framework serves `templates/plugins/<name>/mobile/<template>`
on mobile requests. See Dev-Guide §5.10.

### 9.4 The feedback loop — your plugin can improve the framework

AirDrop's pluginization ran with an explicit goal: **find framework improvements and
file them back**. It surfaced real gaps that shipped in later framework versions:

| Finding | Shipped as |
|---------|-----------|
| `save_uploaded_file` didn't cover sync persistent uploads | `BasePlugin.save_uploads` + `sanitize_filename` (v4.18) |
| description-conflict error listed fields but not values | clearer error (v4.17.2) |
| plugin.json invalid JSON was silently ignored | "描述文件失效" flag (v4.17.2) |
| plugins had no easy dark-mode hookup | `theme_effective` + `theme.css` + `theme.js` (v4.19.1) |

To do this well: keep a **coordination list** (one page linking every framework finding
→ which version fixed it → test/CI to add), and refactor toward framework services
instead of working around them. That loop is what turns a plugin project into a
framework collaborator.

### 9.5 User account self-service (v4.20)

Log-in users can self-manage their own account at **`/user-center`** (page guarded by
the framework so the un-logged-in are redirected to `/login`):

- **Change nickname** — `POST /api/auth/user/update-nickname` with `{nickname}`
  (non-empty, ≤20 chars, whitespace-trimmed).
- **Change password** — `POST /api/auth/change-password` with
  `{old_password, new_password}` (old must match, new ≥6 chars, other sessions kicked).

**Usernames are immutable** (the login id is fixed after creation) and it is **self-service
only** — an admin manages other users through the built-in `user_manage` plugin. The
framework ships a `user_center.html` + `user_center.js` you can link to from your own
navigation; the admin navbar and the public navbar already link to it. If your plugin
needs the current user's nickname, read it from `/api/auth/user/info`.

---

## Appendix A — Pitfalls cheat-sheet

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| `plugin.json` has `#` comments | plugin behaves oddly, capabilities ignored | valid JSON only |
| manifest ↔ class drift (`version`/`description`) | install rejected with field list | bump together |
| `save_uploaded_file` on a sync flow | feels wrong, temp-file semantics | use `save_uploads` |
| high-risk call + capability "fix" | still rejected in enforce | refactor to framework service |
| double CSRF token | 403 on write in auth mode | don't hand-inject; use `plugin_common.js` |
| page guard vs API guard | page redirects to login for public tool | `public_page=True` + public routes |
| wrong `require_framework_version` | install rejected | ≤ running framework, ≥ features used |
| CRLF line endings in manifest/HTML | git noise, rare rendering issues | keep LF (`.gitattributes`) |
| private signing key committed | leaked key | never commit; publish only public key |

## Appendix B — Quick reference

- Page: `/plugin/<name>` · Sub-page: `/plugin/<name>/<sub>` · API: `/api/<name>/<path>`
- Static: `/plugin-static/<name>/<file>`
- Templates: `templates/plugins/<name>/` · Static: `templates/plugins/static/<name>/`
- Plugin config: `plugins/configs/<name>.json`
- `@permission("public" | "user" | "admin")`, `public_page` class attr
- Reuse: `save_uploads`, `sanitize_filename`, `send_file_response`, `check_upload`, `check_upload_limit`, `get_data_path`
- Theme: `{{ theme_effective }}` + `theme.css` + `theme.js`
- Tools: `package.py pack/verify/genkey`, `install_plugin.py backend [--update]`, `scan.py`, `config.py set`

## Appendix C — Example plugins (run them to see patterns)

| Example | Shows |
|---------|-------|
| `hello_plugin` | minimal skeleton, lifecycle, 3-level permission, sub-pages, config |
| `scheduler_demo` | scheduled tasks (`scheduler`) |
| `async_file_demo` | async upload → process → download chain (`save_uploaded_file`/`run_async_task`) |
| `dependent_demo` | cross-plugin events & dependency resolution |
| `multitool_demo` | large multi-page plugin + dark-mode three-piece hookup (v4.19+) |
| `corp_tools` | enterprise toolset: health check, tool nav, async board (multi-template/permission/scheduler/config/data-dir) |
| `root_demo` | framework **Root** permission domain (`framework:core`) |

> **Frontend tool packages** (`examples/frontend_tools/dashboard_demo`) are the simpler,
> self-contained counterpart to backend plugins — not covered in this tutorial, see the
> Dev Guide's frontend-tools section.

Install with `python examples/install_all.py` in the source checkout, or pack any of
them and `install_plugin.py backend`.

## Appendix D — Where the Dev Guide covers each part

| This tutorial | Dev-Guide (Flask-Plugin-Framework-Dev-Guide-v4.md) |
|---------------|---------------------------------------------------|
| Part 0 plugin anatomy | §3.2, §6.1 |
| Part 1 runtime & tools | §2, §2.2 |
| Part 2 first plugin | §6.1.1, §4 |
| Part 3 pages & frontend | §6.3, §8, §4.5 |
| Part 4 APIs & data | §4, §5.4, §5.4.2 |
| Part 5 auth & permissions | §3.5, §8 |
| Part 6 capabilities & strict | §10.7, §10.6, §2.4 |
| Part 7 packaging & distribution | §6, §10.5 |
| Part 8 iteration & release | §9, Release-Wrapup-Checklist.md |
| Part 9 theme/i18n/mobile | §5.11, §7, §5.10 |

---

> **Worked reference implementation:** the AirDrop plugin
> ([github.com/ReconLeo/AirDrop](https://github.com/ReconLeo/AirDrop)) was pluginized
> exactly along this tutorial's path — `plugin/` (dev source), `package/` (distribution
> source), signed release zips, dark-mode via the three-piece hookup, and a
> `docs/框架改进-save_uploads-API设计.md` showing the feedback loop. Read it side by
> side with each Part.
