# 隔离框架副本开发

当用户要求「在框架副本内开发」「复制框架做隔离测试」「先搭个副本验证」时使用本页。核心目标：**不在主框架运行时内随意安装/卸载/重置**，避免污染主框架运行时、干扰主项目回归；副本可随意折腾，验证通过后再同步回主框架。

## 为什么需要副本

- 插件/功能开发期的真实环境测试（安装/卸载/升级/重置）有副作用，在主框架运行时内做会污染。
- 子项目插件打包安装验证应在隔离副本进行。
- 副本验证通过后再同步主框架运行时部署副本（3 处：`plugins/`、`templates/plugins/<name>/`、`templates/plugins/static/<name>/`）并重启服务。

## 获取最新 runtime：两种途径（路径不硬编码，向用户确认来源）

### 途径 A：从 GitHub release 下载
```
# 占位符，用户提供/确认实际 URL
{RUNTIME_URL} = https://github.com/ReconLeo/FlaskToolkit/releases/download/vX.Y.Z/FlaskToolkit-X.Y.Z-runtime.zip
curl -L "{RUNTIME_URL}" -o "{RUNTIME_ZIP}"
```
- 版本 X.Y.Z 应与当前发布版本一致（以 changelog.json 或用户指定为准）。

### 途径 B：从仓库 `releases/` 目录取现成包
- 仓库根 `releases/` 下可能已有现成 runtime zip（如 `FlaskToolkit-4.23.1-runtime.zip`）。
- **必须核查版本与 sha256 一致性**：把本地 zip 的 sha256 与 `changelog.json` 中记录的 `sha256` 比对，确认拿到的是当前发布包、未被改过。
```
sha256sum "{RUNTIME_ZIP}"
```

### 版本核查（两种途径都要）
1. 解压后看 `global_var.py` 的 `FRAMEWORK_VERSION` 或 `SYSTEM_VERSION_LABEL`，确认为目标版本。
2. 与 `changelog.json` 的 `latest_version` / `sha256` 交叉核对。
3. 若不一致，向用户说明并确认用哪个版本，**不擅自换包**。

## 搭建副本

1. 解压 runtime zip 到隔离目录 `{COPY_ROOT}`（副本根，与主框架分开）。
2. 副本根应含 `app.py`、`core/`、`tools/`、`plugins/`、`templates/` 等完整运行时结构。
3. 如需完整源码/文档/测试做开发，用 `--full` 全量包或直接复制主框架源码（见下）。

## 在副本内开发/验证

- 副本内可用系统 Python 启动服务、安装插件包（`tools/install_plugin.py` 或运行时上传）、卸载、重置，随意折腾。
- 启动/打包仍用系统 Python 并清空 PYTHON* 变量（见 [local-env.md](local-env.md)）。
- 需要开发调试时，可直接把主框架源码复制成副本（不在主项目内测试），或复制全量 runtime。

## 验证后同步回主框架

副本验证通过后，把改动同步到主框架运行时部署副本：
- `plugins/`、`templates/plugins/<name>/`、`templates/plugins/static/<name>/` 三处部署副本同步（保持 LF）。
- **重启服务**，重新登录建立会话，做端到端确认。

## 与子项目开发的关系

独立子项目插件的源在主框架 examples/ 之外；副本用于安装测试，主框架只保留运行时部署副本。字段一致性、打包、LF 等约定见 [example-plugins.md](example-plugins.md)。
