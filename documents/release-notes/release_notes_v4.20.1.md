## v4.20.1 — 修复 update_checker + selfcheck themes/tzdata（覆盖发布）

### 修复 1：update_checker 有缓存重启后未重新远程获取
- `background_check()` 改为 `check_for_update(force=True)`：启动低频事件绕过缓存 TTL（默认 24h），每次重启**强制拉取最新版本并写缓存**；TTL 仍用于抑制运行中手动非强制检查。

### 修复 2：themes 误入 CORE_DIRS 致新装框架无法启动
- v4.19.2 把 `themes` 加进 `CORE_DIRS`（缺失视为致命），而 themes 是**可选扩展目录**（无自定义主题时不存在属正常），导致新装（runtime 无 themes）启动时 selfcheck 误报"核心目录缺失: themes"致命。
- 修复：`themes` 从 `CORE_DIRS` 移出（selfcheck 不强求存在）；归入 `USER_DATA_PATHS`（升级/备份保留用户自定义主题）；`RUNTIME_TOP` 不含 themes（可选目录，源码自带 `themes/sepia` 作自定义主题模板，runtime 用户可复制/自行添加）。

### 修复 3：tzdata 加入 selfcheck REQUIRED_DEPS
- `core/selfcheck.py` `REQUIRED_DEPS` 补 `tzdata`（APScheduler 3.11 用标准库 zoneinfo，Windows 缺 tzdata 时 app.py 顶层创建 scheduler 即崩；requirements.txt 已锁 tzdata==2026.3）。

### 测试
- `test_update_checker` 50→52（背景检查强制远程获取）、`test_selfcheck` 14→17（A4/A5/A6：themes 不在核心必需 / 在 USER_DATA_PATHS / tzdata 在 REQUIRED_DEPS）、`test_framework_manifest` E1 补 themes 53→54。
- 全量回归 **47 脚本 1227 项 0 失败**。
- runtime 包 sha256：`877e2e393d38d48263cef97dce7f837329595fff95aa76af0d07fa62a92c4bc4`
