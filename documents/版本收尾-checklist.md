# 版本收尾 Checklist（可复用）

> 每次框架版本发布前，按本清单逐项检查，防止"功能改了、配套没跟上"的漂移。
> 首次沉淀自 v4.5.0（HTTPS + frontend_tools.json 迁移 + 检修）与 v4.5.1（登录锁定手动解封）两次收尾实践。

---

## 1. 版本号三处同步（铁律）

| 位置 | 检查点 |
|------|--------|
| `global_var.py` | `FRAMEWORK_VERSION = "x.y.z"` |
| `tests/test_admin_api.py` | 框架版本断言同步 |
| `README.md` / `README.zh-CN.md` | 徽章版本号（**双版本都要改**） |

> **坑**：README 英文版徽章断言附近存在特殊加粗边界（`**N-assertion regression suite and GitHub Actions CI**`），批量替换时常漏，已多次出现——替换后务必 grep 复核三处。

## 2. 配置项核对

新增/变更配置后检查：

- [ ] `global_var.py`：模块级常量 + `CONFIG_ITEMS` 注册（含 `kind`，如 `path`/`int`/`str`/`bool`）
- [ ] `tools/config_cli.py`（或等价 CLI）能显示/修改新配置
- [ ] 文档 `开发规范` 的配置章节（10.x）同步新配置项
- [ ] 默认值语义明确（如 HTTPS 证书路径为空 = HTTP）

## 3. 数据路径迁移点

若本次版本移动了运行时数据文件（如 frontend_tools.json、auth sessions），逐项核对：

- [ ] 新路径常量定义（`data/frontend_tools.json` 等），旧路径保留兼容
- [ ] 启动/加载时自动迁移逻辑（`os.replace` 原子迁移，双份并存时告警）
- [ ] `core/factory_reset.py`：reset 范围同步新路径 + 兼容删除旧文件
- [ ] `tools/backup.py`：`BACKUP_ITEMS` 指向新路径
- [ ] `tests/ci_cleanup.py` 及引用旧路径的测试全部同步
- [ ] 示例插件内硬编码路径（如 `RESULT_DIR`）改用 `self.get_data_path(...)`
- [ ] `.gitignore`：新运行时目录（如 `data/certs/`）不入库
- [ ] `core/selfcheck.py`：若文件由入库转为运行时配置，从 `CORE_FILES` 致命清单移除（缺失不致命）

## 4. 检修文件一致性

每次版本迭代后确认以下"体检"文件跟上新模块：

- [ ] `core/selfcheck.py` `CORE_FILES`：新增的核心模块全部纳入（历次漏过：plugin_scanner / capabilities / audit_hook / plugin_cache / plugin_status / routes / security.py）
- [ ] `core/audit_hook.py`：框架自管目录（logs/data/backups/temp）路径过滤，避免 enforce 模式崩溃
- [ ] `core/factory_reset.py`：新增目录/文件纳入 reset 范围
- [ ] `tools/` 内部工具：backup 清单、深度重置、配置 CLI 无过时路径
- [ ] `plugins/user_manage.py`、内置插件：确认无自有文件操作或已走框架 API

## 5. 示例插件同步（开发规范 10.7 维护约定）

- [ ] `examples/plugins/*/plugin.json` 与主 `.py` 类属性**两处一致**（name/version/title/description/author/category/permission/dependencies/require_framework_version）
- [ ] `require_framework_version` 高于所用框架 API 的引入版本（如使用 `get_data_path` 要求 ≥ 4.3.2）
- [ ] `capabilities` 声明与实际行为匹配（`scheduler` 等；自属路径读写隐式豁免无需声明）
- [ ] 示例内容变更时同步升级 `version`（保证 update 可重复安装）
- [ ] `examples/README.md`、`examples/manifest.json` 描述与路径无过时信息
- [ ] `examples/install_all.py --pack-only` 打包验证通过

## 6. 行尾与文件编辑

- [ ] 改文件前检测行尾（`file` / python 统计 `\r\n`）：`routes/`、`plugins/base_plugin.py`、`plugins/user_manage.py`、`templates/plugins/*.html`、`tools/backup.py` 为 **CRLF**；`core/*.py`、`app.py`、`global_var.py`、`tests/*.py`、`plugins/auth.py` 为 **LF**
- [ ] CRLF 文件脚本处理：`io.open(newline='')` 读原始行尾 → 编辑 → 按 has_crlf 还原
- [ ] file edit 对顶层定义间空行数敏感（两个空行），连续失败改 python 脚本 read→replace→write
- [ ] 复杂脚本（中文长文本/heredoc）先 file write 落盘再 python 执行，防截断

## 7. 回归与验证

- [ ] 全量回归：`for t in tests/test_*.py; do python $t; done`（当前 22 脚本 497 项）
- [ ] 新增功能专项测试通过（如 test_capabilities / test_security / test_page_router）
- [ ] `python examples/install_all.py --pack-only` 打包校验
- [ ] `python tools/selfcheck.py`（或等价）启动自检通过
- [ ] 冒烟验证新功能端到端（必要时 app.test_request_context / test_client）

## 8. 文档双同步

- [ ] `documents/Flask插件框架开发规范-v4.0.md`：版本标题/版本说明/新章节/目录树（主要更新点）
- [ ] `README.md`（英文主版）+ `README.zh-CN.md`（中文版）：亮点、断言数、徽章、示例表（**双版本同步**，勿只改一处）
- [ ] `documents/Flask插件框架-Roadmap-v4.1.md`：版本对照表（当前版本行 + 已完成行；注意多行编辑顺序勿覆盖旧行）
- [ ] 两文档内容边界：README=门面（精简），开发规范=权威规格（目录树/详细规格唯一出处）

## 9. 提交与推送

- [ ] `git status` 核对变更文件清单（无意外文件、无 .gitignore 遗漏产物）
- [ ] commit message 惯例：`feat(vX.Y.Z): 摘要`（或 fix 前缀）
- [ ] push 到 main 分支

## 10. 记忆与知识沉淀

- [ ] 记忆总览页新增版本章节（**注意上限 ~10000 字符，超限拆分子页**）
- [ ] 历史演进索引页新增版本行 + 子页详情条目（含踩坑经验）
- [ ] README 断言数 / 测试脚本数与记忆数据一致
