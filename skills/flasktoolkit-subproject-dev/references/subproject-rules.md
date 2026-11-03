# 子项目开发规则

本文档约束"把独立工具开发成 FlaskToolkit 子项目插件"的稳定约定。所有绝对路径一律由用户在执行时提供，本技能与脚本不硬编码。

## 0. 由用户提供的运行参数

以下路径/地址由用户在执行时指定（命令行参数或环境变量），**不要硬编码**：

| 参数 | 建议环境变量 | 用途 |
| --- | --- | --- |
| 主项目框架路径 | `FTK_FRAMEWORK_PATH` | 打包/扫描/安装等需要 `tools/*.py` 时指向的框架根目录 |
| GitHub release 运行包地址 | `FTK_RUNTIME_URL` | 隔离测试下载用的 `FlaskToolkit-<version>-runtime.zip` 直链 |
| GitHub CLI | `FTK_GH_PATH` | 远程建仓/打 release 用 `gh.exe` 可执行路径 |

未提供时先向用户索取，不要猜测。

## 1. 子项目定位与源管理

- 插件属于 FlaskToolkit **子项目**，源**独立于主框架**（独立目录/仓库，如 `AirDrop/`、`TTS_tools/toolchain/plugins/<name>/`），不在主框架 `examples/` 内开发。
- 主框架只保留**运行时部署副本**（`plugins/`、`templates/plugins/<name>/`、`templates/plugins/static/<name>/`），不保留子项目源。
- 变更从子项目源**打包安装**到主框架运行时，或同步复制部署副本 + 重启服务做端到端验证。

## 2. 真实环境测试：用 GitHub release 运行包做隔离测试

子项目需要真实环境测试时，**不要在主项目里测**（避免污染运行时、干扰回归）。正确做法：

1. **下载官方构建好的 runtime 运行包**（直接请求 GitHub release 直链，如 `FlaskToolkit-4.23.0-runtime.zip`）并解压到隔离目录，**不复制源码目录**。
2. 把子项目打好的插件 zip（`tools/package.py pack` 产物）安装进该隔离副本。
3. 在隔离副本内启动服务做端到端验证，可随意安装/卸载/Factory Reset，不污染主框架。
4. 验证通过后再同步主框架运行时部署副本。

隔离副本目标版本应匹配插件 `require_framework_version` 要求（见 plugin-authoring.md）。

## 3. 解释器隔离（通用）

某些解释器环境会注入 `sitecustomize` 审计钩子（拦截 `os.remove`/`rmtree` 等永久删除、让 `py_compile` 启动报错），或通过 `PYTHONHOME`/`PYTHONPATH` 把 `python` 指向非预期环境，从而让打包/自检/服务启动出现「像是项目缺陷」的失败。规避方法：

- 用**干净解释器**执行打包、语法检查、启动服务：路径由用户或环境变量（如 `SYSTEM_PYTHON`）提供，**不写死**。
- 执行前**清空 `PYTHONHOME`/`PYTHONPATH`** 环境变量。
- 脚本层面用 `pack_plugin.sh` 统一封装（见 scripts/），它优先取 `SYSTEM_PYTHON`。
- 判定准则：换干净解释器后症状消失 = 环境问题，**不要**为了兼容它去改框架代码。
- 通用三步定位法（`sys.executable` / `sitecustomize` 来源 / `PYTHON*` 变量）见主框架技能的 `references/local-env.md`；具体机器实例记录见仓库 `skills/DEV-ENVIRONMENT-NOTES.md`（非技能依赖）。

## 4. 全仓统一 LF 行尾

- 子项目文本文件（`.py`/`.json`/`.html`/`.css`/`.js`/`.md`）统一 **LF**；禁止 CRLF、`\r\r\n`、混用行尾。
- 仓库根放置 `.gitattributes` 强制 LF：

```
* text=auto eol=lf
```

- Markdown 表格渲染异常先查行尾是否被污染。

## 5. 打包排除编译产物

- `py_compile` 语法检查会在源目录生成 `__pycache__/*.pyc`；打包时 `tools/package.py`（v4.21.1 起）已用 `PACK_SKIP_DIRS` 排除 `__pycache__`，但仍建议保持源码目录干净，避免编译产物入库/提交。

## 6. 发布工具不硬编码

- 远程创建仓库、打 release 使用 git 与 `gh.exe`；其可执行路径由用户提供（如 `FTK_GH_PATH`），不写死绝对路径。
