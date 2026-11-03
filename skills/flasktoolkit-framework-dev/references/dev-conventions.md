# 开发纪律：行尾、版本号、文档同步

本页固化主框架开发的稳定约定。所有文本文件统一 **LF**（`.gitattributes` 强制）；版本号与文档有严格的同步点。

## 1. 行尾规则（.gitattributes 强制）

- 文本文件统一 **LF**；禁止 CRLF、`\r\r\n`、混用行尾。Markdown 表格渲染异常先查行尾。
- **历史 CRLF 文件**（编辑时须按原行尾还原）：
  - **CRLF**：`routes/`、`plugins/base_plugin.py`、`plugins/user_manage.py`、`templates/plugins/*.html`、`tools/backup.py`
  - **LF**：`core/*.py`、`app.py`、`global_var.py`、`tests/*.py`、`plugins/auth.py`
- 脚本处理 CRLF 文件：`io.open(path, newline='')` 读原始行尾 → 编辑 → 按 `has_crlf` 还原。
- file edit 对顶层定义间空行数敏感（两个空行）；连续失败改 Python 脚本 read→replace→write。
- 复杂脚本（中文长文本/heredoc）先 file write 落盘再 Python 执行，防截断。

## 2. 版本号五端点同步（铁律）

发布/改版本时，以下五处必须一致（`tools/release.py bump --version X.Y.Z` 自动同步其中三处 + 徽章）：

| 端点 | 位置 | 说明 |
|------|------|------|
| `FRAMEWORK_VERSION` | `global_var.py` | 后端比较基准（插件 require_framework_version 对照） |
| `SYSTEM_VERSION_LABEL` | `global_var.py` | 前端展示标签（vX.Y.Z） |
| 框架版本断言 | `tests/test_admin_api.py` | 回归断言同步 |
| README 徽章 | `README.md` + `README.zh-CN.md` | **双版都要改**，英文版徽章存在特殊加粗边界，改后 grep 复核 |
| 框架清单 | `core/framework_manifest.py` | 核对/更新 |

> 坑：README 英文版徽章批量替换时常漏；替换后务必 grep 复核三处。

## 3. 文档双同步

| 文档 | 角色 | 同步要求 |
|------|------|---------|
| `README.md` / `README.zh-CN.md` | 门面（精简） | 亮点、断言数、徽章、示例表**双版同步**；README 只维护脚本总数与断言总数，不维护逐脚本清单 |
| `documents/Flask-Plugin-Framework-Dev-Guide-v4.md` | 权威规格（目录树/详细规格唯一出处） | 新增功能/示例/测试后同步新章节与目录树；**不写版本说明/版本线** |
| `documents/Flask-Plugin-Framework-Changelog.md` | **历史演进唯一出处** | 发布时新增版本小节 + 版本线总览表；dev guide 不承载演进史 |
| `documents/Flask-Plugin-Framework-Roadmap-v4.md` | 版本对照表 | 当前版本行 + 已完成行 |

## 4. changelog.json 强制同步

- `changelog.json` 是更新检查元数据（`latest_version` / `published_at` / `download_url` / `sha256` / `changes`）。
- **必须随 Release 一起 commit + push**（曾漏导致版本数据缺失）。

## 5. 新增/变更配置项

- `global_var.py`：模块级常量 + `CONFIG_ITEMS` 注册（含 `kind`，如 path/int/str/bool）。
- `tools/config.py`（或等价 CLI）能显示/修改新配置。
- 开发规范配置章节（10.x）同步新配置项。
- 默认值语义明确（如 HTTPS 证书路径为空 = HTTP）。

## 6. 数据路径迁移

移动运行时数据文件时逐项核对：新路径常量定义 + 启动迁移逻辑（`os.replace` 原子迁移）+ `core/factory_reset.py` reset 范围 + `tools/backup.py` BACKUP_ITEMS + 测试引用 + 示例插件硬编码路径改 `self.get_data_path(...)` + `.gitignore` 新运行时目录不入库 + `core/selfcheck.py` 致命清单调整。

## 7. 检修文件一致性（每版迭代后确认）

`core/selfcheck.py` `CORE_FILES`（新增核心模块全部纳入，历次漏过 plugin_scanner/capabilities/audit_hook/plugin_cache/plugin_status/routes）、`core/audit_hook.py` 框架自管目录路径过滤、`core/factory_reset.py` reset 范围、`tools/` 内部工具无过时路径、内置插件走框架 API。
