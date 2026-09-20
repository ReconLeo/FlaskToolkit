# FlaskToolkit v4.23.1

安全/健壮性修复批次（来自子插件 todo_quickhelper 安全意识演示的隔离测试），全量回归 49 脚本 0 失败。

## 修复 user_config.json 带 UTF-8 BOM 时配置静默失效（FTK-001）

`user_config.json` 若以 UTF-8 BOM 保存（Windows 记事本 / PowerShell 5.1 `Set-Content -Encoding UTF8` 默认行为），原有 `encoding='utf-8'` 读取会让 `json.load` 抛异常，且多处异常被静默吞掉，后果：

- **安全开关静默降级**：`AUDIT_HOOK_MODE=enforce` 回落到 `observe`，运行时审计防火墙形同未开且无任何告警。
- **静默丢配置**：`tools/config.py set/unset` 读失败后以空 dict 覆盖写回，原文件其它配置项永久丢失。

修复：
- 所有 `USER_CONFIG_FILE` 读取点统一 `encoding='utf-8-sig'`（对无 BOM 文件行为与 `utf-8` 完全一致）：`global_var.py` / `routes/public.py` / `routes/admin.py` / `tools/config.py` / `tools/desktop_launcher.py`。
- `global_var.load_user_config()` 解析失败拆出内层异常处理并 `logging.warning` 留痕，安全开关降级不再无痕。
- `tools/config.py::_load_file` 增加 `strict` 参数；`cmd_set`/`cmd_unset`/`apply_profile` 写回前在解析失败时中止并报错，不再空 dict 覆盖丢配置。

## 修复静态扫描器点分模块名网络调用漏报（FTK-002）

`core/plugin_scanner.py` 对 `urllib.request.*` / `http.client.*` 等**点分模块名**的出站调用全部漏报，两个根因叠加：

- **导入比对只用模块名首段**：`import urllib.request` 记为首段 `urllib`，配不上 `MEDIUM_IMPORTS` 里的 `'urllib.request'`。
- **别名映射重复拼接**：`_import_context` 把 `urllib` 映射成 `urllib.request`，`_full_call_name` 解析出 `urllib.request.request.urlopen`，匹配不上 `MEDIUM_CALLS` 的 `'urllib.request.urlopen'`。

后果是审查者在报告里看不到「该插件会外发」，动态 URL 场景 `scope['network_endpoints']` 为空、交叉校验无从比对。

修复：
- `_import_context` 别名只登记「首段→首段」，让 `_full_call_name` 按属性逐级还原。
- 导入检查同时加入完整名与首段，`urllib.request` / `http.client` / `asyncio.subprocess` 全部命中。
- `MEDIUM_CALLS` 补全 `urllib.request.Request` / `build_opener` / `urlretrieve`。

## 修复离线卸载残留 `plugins/<name>/__pycache__/`（FTK-003）

`core/plugin_pack.py::_delete_installed_files` 按 `installed_files` 清单删除后只剪枝空目录，而 `__pycache__/*.pyc` 是运行时生成的编译产物、从不在清单内，导致卸载后残留一个空壳目录、看起来"没卸干净"。

修复：按清单删除后显式清理 `<base>/plugins/<name>/__pycache__`，再统一剪枝空目录；范围严格限定在插件自有编译产物，不误删插件数据目录。

## 测试与文档

- 新增 6 项回归断言：`test_tools_ops.py`（BOM 下 set 不丢键 / `load_user_config` 读 BOM 后 `AUDIT_HOOK_MODE=enforce`）、`test_plugin_scan.py`（A21–A23 点分模块）、`test_plugin_cleanup.py`（卸载后 `__pycache__` 清理）。
- dev guide 十二章与 README 断言数同步为 49 scripts / **1330** assertions（cleanup 26→27、tools_ops 19→21、scan 43→46）。

**全量回归 49 脚本 0 失败。**

- **Runtime**: `FlaskToolkit-4.23.1-runtime.zip`（精简运行包）
- **sha256**: `7e73d9b9f3521aaf9f7a84fbbe6a8643d7ef7668a77d3b35560e572ea3ae3ab6`
