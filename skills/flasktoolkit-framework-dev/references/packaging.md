# 打包：插件包与 runtime 包

本页覆盖 FlaskToolkit 的两种打包：插件包（单插件分发）与框架 runtime 包（更新/发布用）。均在框架根 `{FRAMEWORK_ROOT}` 下执行，使用系统 Python 并清空 PYTHON* 变量（见 [local-env.md](local-env.md)）。

## 1. 插件包打包

用于把单个插件打成可分发 zip：
```
python tools/package.py pack <src> -o out.zip --type backend
```
- `--type backend` 为后端插件包。
- 自动生成 `manifest.json`（放 zip 内仅供完整性校验，不落盘）。
- v4.21.1 起已用统一 `PACK_SKIP_DIRS` 排除 `__pycache__/.pyc/.pyo`，无需手动清 pyc；仍建议保持源目录干净（避免编译产物入库/提交）。
- 打包前核对字段一致性（plugin.json 与类属性两处一致），见 [example-plugins.md](example-plugins.md)。

## 2. 框架 runtime 包构建

`tools/release.py`（版本号同步 / 更新包构建 / changelog 生成与签名）。

### bump —— 版本号同步
```
python tools/release.py bump --version X.Y.Z
```
自动同步：`global_var.py` FRAMEWORK_VERSION、SYSTEM_VERSION_LABEL、README 徽章（双版）。仍须手动核对 `tests/test_admin_api.py` 断言与 `core/framework_manifest.py`（版本五端点，见 [dev-conventions.md](dev-conventions.md)）。

### build —— 构建更新包 + 写 changelog.json
```
python tools/release.py build --version X.Y.Z \
    --changes "..." --changes "..." \
    --download-url "https://github.com/{owner}/{repo}/releases/download/vX.Y.Z/FlaskToolkit-X.Y.Z-runtime.zip" \
    [--full] [--include /path/src:rel/dest ...] [--sign private.pem] [--out dist]
```
- **需显式传 `--version`/`--changes`/`--download-url`**。
- `--full`：全量包（含 tests/documents/examples）；默认精简运行包（由 `core/framework_manifest.py` 的 RUNTIME_* 白名单决定）。
- `--include`：叠加企业定制附加项（`/path/src:rel/dest`）。
- `--sign`：签名（SHA256 + changelog 签名字段，与 `core/update_checker.SIGNED_FIELDS` 对齐：latest_version/published_at/download_url/sha256/changes）。
- download-url 用 tag 创建后的最终 URL（tag 存在前 URL 暂时 404 但 build 照常写 changelog.json）。

### 打包范围与清单
- 精简包白名单由 `core/framework_manifest.py` 的 `RUNTIME_*` 单一清单提供（原硬编码迁移至此，防漂移）。**新增框架顶层内容必须先登记**（见 [repo-layout.md](repo-layout.md) 关键登记点）。
- `tools/update.py`、`tools/selfcheck.py` 均从 manifest 导入，勿在 tools 内硬编码清单。

## 3. 框架更新（update）

`tools/update.py` 用于框架更新应用（消费 update_feed 下载的包做安装门禁 + 应用）。日常开发一般用 build 产出 runtime 包，update 在更新闭环验证/发布后自检时用。

## 执行环境注意

打包/语法检查/启动服务请用**干净解释器**（路径由调用方提供，如 `SYSTEM_PYTHON`，不写死）并清空 `PYTHONHOME` / `PYTHONPATH`；环境陷阱的通用排查见 [local-env.md](local-env.md)。
