# 主框架目录结构与模块职责

仓库根即框架源码树。权威目录树与详细规格见 `{FRAMEWORK_ROOT}/documents/Flask-Plugin-Framework-Dev-Guide-v4.md` 二、项目结构章节。本页只列开发时最常涉及的模块与登记点。

## 顶层文件

| 路径 | 职责 |
|------|------|
| `app.py` | 应用入口（Flask 应用创建、调度器、启动流程） |
| `global_var.py` | 全局常量与配置项注册；`FRAMEWORK_VERSION`（版本号唯一来源之一）、`SYSTEM_VERSION_LABEL`（前端展示版本） |
| `README.md` / `README.zh-CN.md` | 门面文档（双版同步，见 dev-conventions） |
| `changelog.json` | 更新检查用版本元数据（最新版本/sha256/变更，发布时强制同步） |
| `requirements.txt` / `requirements-dev.txt` | 运行时/开发依赖 |
| `.github/workflows/ci.yml` | CI 回归（TESTS 数组须与 tests/ 脚本一致） |

## 核心模块 `core/`

| 模块 | 职责 |
|------|------|
| `framework_manifest.py` | **单一清单**：CORE_DIRS、USER_DATA_PATHS、RUNTIME_* 白名单等，供自检/升级/备份/重置/打包/Root 判定 |
| `plugin_loader.py` / `plugin_pack.py` | 插件加载 / 插件包（.zip）解包 |
| `plugin_scanner.py` / `capabilities.py` | 静态扫描 / capabilities 白名单（门禁统一判定入口 `evaluate_gate()`，v4.23.5） |
| `audit.py` / `audit_hook.py` | 审计 / 运行时审计钩子 |
| `plugin_admin.py` / `plugin_updates.py` | 程序化插件管理 / 插件级更新源 |
| `events.py` | 自研事件总线（v4.16） |
| `plugin_deps.py` | 插件全量依赖解析 |
| `i18n.py` | 国际化取词 |
| `permission.py` / `device.py` | 三层权限 / 移动端 UA 检测 |
| `network.py` / `mdns.py` / `ip_watcher.py` | 地址中心 / mDNS / IP 变化检测 |
| `stats.py` / `quota.py` | 统计面板 / 配额 |
| `selfcheck.py` | 启动完整性自检（`CORE_FILES` 致命清单——新增核心模块须登记） |
| `update_checker.py` / `package_sign.py` | 版本检查 / 完整性签名 |

## 工具 `tools/`

| 工具 | 用途 |
|------|------|
| `release.py` | bump（版本号同步）/ build（runtime 包+changelog） |
| `package.py` | 插件包打包 `pack <src> -o out.zip --type backend` |
| `update.py` | 框架更新 |
| `run_all_tests.py` | 全量回归（串行跑 tests/test_*.py） |
| `backup.py` / `reset.py` | 备份 / 深度重置 |
| `config.py` | 配置 CLI |
| `scaffold.py` | 插件脚手架 |
| `migrate_plugin_layout.py` | 旧布局迁移 |
| `install_plugin.py` | 插件安装 |
| `i18n_status.py` / `scan_missing_i18n.py` | i18n 状态 / 缺失中文 key 扫描（见 i18n.md） |

## 其它目录

- `routes/`：HTTP 路由。
- `plugins/`：内置/运行时插件部署副本；`base_plugin.py` 为插件基类（BasePlugin）。
- `templates/`：后端模板（含 `templates/plugins/<name>/` 插件模板、`templates/plugins/static/<name>/` 静态资源、`templates/mobile/` 移动端）。
- `static/`：全局静态资源。
- `locales/`：语言包（en.json / zh-CN.json / 其它）。
- `examples/`：示例插件（plugins/）+ 前端工具 + `install_all.py` + `manifest.json`。
- `tests/`：回归测试脚本（test_*.py）。
- `data/`、`logs/`、`temp/`、`uploads/`、`themes/`、`releases/`：运行时数据 / 日志 / 临时 / 上传 / 主题 / 本地 runtime 包。
- `documents/`：权威文档（开发规范、changelog、交接、checklist）。

## 关键登记点：新增文件必须同步

新增**框架顶层/核心内容**时，核对 `core/framework_manifest.py`：
- `RUNTIME_TOP` / `RUNTIME_EXAMPLE_THEME` / `RUNTIME_PLUGIN_FILES` / `RUNTIME_PLUGIN_DIRS` / `RUNTIME_TEMPLATE_EXCLUDE` —— 精简运行包白名单（单一清单，漏登记致精简包漏带）。
- `CORE_FILES`（自检致命清单）、`CORE_DIRS`、`USER_DATA_PATHS` 按需同步。
- `tools/package.py`、`tools/release.py`、`tools/update.py`、`tools/selfcheck.py` 均从 manifest 导入，**勿在 tools 内硬编码清单**。

> 新增框架文件后务必读 [framework-copy.md](framework-copy.md) / [packaging.md](packaging.md) 确认进包方式，且核对 `tools/package.py` 的 `PACK_SKIP_DIRS` 已自动排除 `__pycache__`（v4.21.1 起，无需手动清 pyc）。
