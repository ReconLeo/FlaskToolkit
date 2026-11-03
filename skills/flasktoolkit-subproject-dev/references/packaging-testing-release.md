# 打包、测试与发布规范

覆盖子项目从源码到可分发插件包、隔离测试、运行时同步、版本发布的完整链路。所有绝对路径（框架根、runtime 包、gh.exe）由用户提供，不硬编码。

## 0. 运行环境

执行打包/扫描/安装/启动前，用系统 Python 并清空 `PYTHONHOME`/`PYTHONPATH`（见 subproject-rules.md §3）。可用 `pack_plugin.sh` 封装。

## 1. 打包 tools/package.py

框架 `tools/package.py` 提供 genkey / pack / verify / show 四子命令（在用户指定的框架根下执行）：

```bash
# 1. 生成密钥对（仅需签名时）
python tools/package.py genkey -o private.pem --pub public.pem

# 2. 打包（自动生成 manifest.json；--sign 用私钥签名）
python tools/package.py pack ./my_plugin -o my_plugin.zip --type backend
python tools/package.py pack ./my_plugin -o my_plugin.zip --type backend --sign private.pem --signer "张三"
#    源码布局自动映射（v4.17.2）：<name>.json+<name>.py+frontend/ → plugin.json+主.py+templates/static
python tools/package.py pack ./my_plugin -o my_plugin.zip --type backend --src-layout

# 3. 校验（完整性 + 可选签名）
python tools/package.py verify my_plugin.zip --public-key public.pem

# 4. 查看包内容与清单状态
python tools/package.py show my_plugin.zip
```

- 打包类型：`--type backend`（插件包）/ `--type frontend`（前端工具，默认）。
- `--src-layout`（仅 backend）：源码布局 `<name>.json`+`<name>.py`+`frontend/` → 分发布局 `plugin.json`+主.py+`templates/static`；自动排除 `configs/`、`__pycache__/`、`temp/`、`.git/`、`node_modules/`、`tests/`。
- 非 src_layout 分支自 v4.21.1 起同样排除 `__pycache__` 与 `.pyc/.pyo`。
- `--exclude GLOB` 可追加排除。

### 完整性清单 manifest.json

pack 自动生成（含全部成员 sha256，可选 RSA 签名）。`PACKAGE_INTEGRITY_MODE`（默认 `warn`，`strict` 强制缺清单拒绝）；签名由框架配置 `PLUGIN_PUBLIC_KEY_PEM` 后强制验证。

## 2. 框架新增文件核对（framework_manifest.py）

新增框架文件（core/、tools/、routes/、templates/、plugins/ 等源码/模板）时，核对 `core/framework_manifest.py`：

- **作用判定**：框架必需 → 入 `CORE_FILES`（单文件）/ `CORE_DIRS`（顶层目录）；非必需/用户数据 → `USER_DATA_PATHS` / `ROOT_RUNTIME_FILES` 或不定级。
- **打包判定**：精简运行包白名单由 `RUNTIME_TOP` / `RUNTIME_EXAMPLE_THEME` / `RUNTIME_PLUGIN_FILES` / `RUNTIME_PLUGIN_DIRS` / `RUNTIME_TEMPLATE_EXCLUDE` 组成。**新增框架顶层文件/目录须在这些 `RUNTIME_*` 同步登记**（漏登记 → 精简包/更新包漏带）；`documents/` 不在精简包内。
- `release.py` / `update.py` / `selfcheck.py` 均从 manifest 导入清单，勿在 tools 内硬编码。

## 3. 字段一致性核对清单（装不上必查）

每次改动插件元信息后核对（结合 plugin-authoring.md §5）：

1. `plugin.json` 与主 `.py` 插件类属性两处一致（name/version/title/author/permission/category/description/dependencies/require_framework_version）；冲突 → HTTP 400。
2. `require_framework_version` ≤ 当前框架版本；用新版能力先 bump 框架。
3. `capabilities` 与实际行为匹配；自属路径隐式豁免无需声明；`save_uploads` 落盘目录建议声明 `filesystem:write:<相对路径>`。
4. 打包产物 + 插件内 manifest/README/en.json 同步；写文件保持 LF。
5. 新增 `{{ t('...') }}` 模板文案须补进 `locales/en.json`（json 注意合法逗号）。

可运行 `validate_plugin.py` 自动校验 1-4 部分。

## 4. 隔离测试流程

1. 下载框架官方 **runtime 运行包**（`FlaskToolkit-<version>-runtime.zip`，GitHub release 直链由用户提供）并解压到隔离目录，不复制源码。
2. `python tools/install_plugin.py install-backend <my_plugin.zip> --base <隔离框架根>`（离线安装；`--no-scan` 跳过扫描、`--update` 更新模式）。
3. 启动隔离副本服务，浏览器/HTTP 端到端验证（登录 admin + 上传 zip + 访问 `/plugin/<name>` + 静态资源 + API）。
4. 可随意卸载 / Factory Reset，不污染主框架。

离线安装 CLI（`tools/install_plugin.py`，需指定 `--base`）：

```bash
python tools/install_plugin.py install-backend <pack.zip> --base <框架根> [--update] [--no-scan]
python tools/install_plugin.py install-frontend <pack.zip> --base <框架根> [--update]
python tools/install_plugin.py uninstall-backend <name> --purge-data --base <框架根>
python tools/install_plugin.py list --base <框架根>
```

## 5. 运行时同步

改源码后如需在主框架做端到端验证，把修改同步到主框架运行时部署副本 3 处，并**重启服务**、重新登录建立会话：

1. `plugins/<name>/`
2. `templates/plugins/<name>/`
3. `templates/plugins/static/<name>/`

部署副本保持 LF。重启后访问管理页确认插件已加载、页面/静态资源/API 正常。

## 6. 发布与版本收尾 checklist

发布前核对（发布流程详见记忆 `FlaskToolkit-发布与版本收尾流程`）：

- [ ] 版本号：`global_var.py` 版本、README 徽章、changelog.json 一致
- [ ] `framework_manifest.py` 版本（若改框架文件）
- [ ] 全量回归：隔离副本或 CI 跑 `tools/run_all_tests.py`，逐脚本通过
- [ ] 打包产物 + manifest/README/en.json LF
- [ ] 历史演进页（`Flask-Plugin-Framework-Changelog.md` 新增版本小节 + 版本线总览）与版本页同步；dev guide 不写版本说明
- [ ] 记入记忆索引 2 并更新核心记忆版本状态

## 7. 远程建仓与发布（git / gh.exe）

- 远程创建仓库、打 release 用 git 与 `gh.exe`；`gh.exe` 可执行路径由用户提供（如 `FTK_GH_PATH`），不硬编码。
- 子项目独立建仓：`git init` + `.gitattributes`（强制 LF）+ `.gitignore`（排除 `__pycache__`/`temp/`/`keys/` 私钥等）+ 首次 commit + `gh repo create`。
- 打 release：`git tag <vX.Y.Z>` + `gh release create <tag> <dist>.zip`。
- 私钥（`keys/*.pem`）务必不进版本库，加入 `.gitignore`。
