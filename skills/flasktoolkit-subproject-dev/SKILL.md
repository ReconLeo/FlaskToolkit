---
name: flasktoolkit-subproject-dev
description: 自动开发 FlaskToolkit 子项目插件（后端 Python 插件 / 前端 HTML 工具包），覆盖全生命周期：环境准备、脚手架、插件编写（plugin.json+主py+模板+静态+能力声明）、字段一致性核对、打包、基于 GitHub release runtime 包的隔离测试、运行时同步与发布收尾。适用于用户要求"开发/扩展/升级/打包/测试/发布某个 FlaskToolkit 子项目插件或工具"时。
disable-model-invocation: false
---

# FlaskToolkit 子项目开发

把独立工具开发为 FlaskToolkit 子项目插件的全流程。编码 agent 按下列阶段推进；详细规则按需读取 references/ 对应文件。

## 工作前必读与运行参数

先向用户索取以下路径/地址（不硬编码），未提供则停下来询问：

| 参数 | 建议环境变量 | 用途 |
| --- | --- | --- |
| 主项目框架路径 | `FTK_FRAMEWORK_PATH` | 打包/扫描/安装用 `tools/*.py` |
| GitHub release runtime 包地址 | `FTK_RUNTIME_URL` | 隔离测试下载 |
| GitHub CLI | `FTK_GH_PATH` | 远程建仓/打 release |

执行任何打包/安装/启动前，用**干净解释器**（路径由用户/`SYSTEM_PYTHON` 提供，不写死）并清空 `PYTHONHOME`/`PYTHONPATH`。为什么、怎么判定环境问题 vs 项目问题：见 [subproject-rules.md](references/subproject-rules.md) §3。

## 附带任务（强制）：查找主框架 bug，找到写可复现协调清单

开发子插件插件时，**同时负有查找主框架 bug 的意图**（约定，非可选项）。每完成一个阶段，主动用真实使用路径审视框架行为，识别是插件问题还是框架问题：

- 隔离测试阶段是找框架漏洞的高效手段——用真实使用路径（尤其安全意识演示/边界场景）能暴露框架健壮性盲区，比专项测试更贴近实际。
- **找到框架 bug/缺陷后必须写一份协调清单**（可复现），格式见 [known-framework-issues.md](references/known-framework-issues.md) §D：现象 → 根因（定位到模块/行）→ 可复现场景（最小步骤）→ 影响面与建议 → 沉淀为 `wiki/lessons/` 页面并附复现场景。
- **避坑先行**：动手前先对照 [known-framework-issues.md](references/known-framework-issues.md) 已知缺陷清单，避免重复踩坑或误判（该文件已由记忆 lessons 提炼，含已修复/未修复两类）。
- 未修复缺陷既要写插件内 workaround，也要上报协调清单。

（已修复的缺陷→插件侧通常无需规避但要知道现象以免误判；未修复的→插件内 workaround + 上报。）

## 阶段工作流

### 1. 环境准备
用干净解释器（`SYSTEM_PYTHON` 或调用方指定，不写死路径）+ 清空 `PYTHONHOME`/`PYTHONPATH`；确认框架根与目标版本。

### 2. 脚手架
在子项目源目录（独立于主框架，不在 examples/ 内）用框架 `tools/scaffold.py` 生成 backend/frontend 骨架，或复制本技能 `assets/plugin-skeleton/` 起步。详见 [plugin-authoring.md](references/plugin-authoring.md) §2 与 [packaging-testing-release.md](references/packaging-testing-release.md) §1。

### 3. 插件编写
按 [plugin-authoring.md](references/plugin-authoring.md) 编写：插件包结构、plugin.json 字段、主 py 类属性、权限三层、capabilities 能力声明、BasePlugin 能力、页面路由、i18n、前端工具 config.json。**插件基类必须绝对导入 `from plugins.base_plugin import BasePlugin`**——该文件位于上级包 `plugins/`，写成相对导入 `.base_plugin` 会 `ModuleNotFoundError`，且**安装期无告警、只在启动加载时炸**，插件会从注册表消失、页面 404（详见 plugin-authoring.md §2 与 known-framework-issues.md §B4）。

编写前先对照 [known-framework-issues.md](references/known-framework-issues.md) 已知缺陷，主动规避；遇到疑似框架问题按“附带任务”写协调清单。

### 4. 字段一致性核对（装不上必查）
运行 `python scripts/validate_plugin.py <src_dir> --framework-root <框架根>`：自动校验 plugin.json 与类属性冲突、name 三处一致、require ≤ 当前版本、capabilities 合法性、LF、无 pycache。不通过先修复再进入打包。

### 5. 打包
用 `scripts/pack_plugin.sh` 封装（自动用系统 Python + 清 PYTHON*）调 `tools/package.py pack`；产物 zip + manifest。需要签名时先 `genkey`，pack 带 `--sign`。改框架文件时同步核对 `core/framework_manifest.py`。详见 [packaging-testing-release.md](references/packaging-testing-release.md) §1-2。

### 6. 隔离测试（不在主项目测）
下载 GitHub release 的 **runtime 运行包**（`FlaskToolkit-<version>-runtime.zip`，由用户提供直链）解压到隔离目录，用 `tools/install_plugin.py install-backend <zip> --base <隔离根>` 安装，启动服务做端到端验证。详见 [packaging-testing-release.md](references/packaging-testing-release.md) §4。

### 7. 运行时同步
验证通过后，把源同步到主框架运行时部署副本 3 处（`plugins/<name>/`、`templates/plugins/<name>/`、`templates/plugins/static/<name>/`），重启服务、重新登录验证。详见 [packaging-testing-release.md](references/packaging-testing-release.md) §5。

### 8. 发布收尾
发布前核对 checklist（版本号/README 徽章/manifest LF/全量回归/历史演进页/记忆索引）。远程建仓与打 release 用 git + `gh.exe`（路径由用户提供）。详见 [packaging-testing-release.md](references/packaging-testing-release.md) §6-7。

## 关键约束速记

- 源独立于主框架，不在 examples/ 内开发；主框架只留运行时部署副本。
- 隔离测试一律用 GitHub release runtime 包，不复制源码、不在主项目测。
- 全仓 LF；`.gitattributes` 强制 `* text=auto eol=lf`。
- 类属性与 plugin.json 两处一致，`require_framework_version` ≤ 当前框架。
- capabilities 白名单声明；自属路径隐式豁免；`eval/exec/pickle/subprocess/socket.bind` 不可约束恒阻断。
- 发布工具与框架路径均由用户提供，不硬编码。
- 附带任务：查找主框架 bug，找到写可复现协调清单（现象/根因/可复现场景/影响建议），沉淀 lessons。

## 资源索引

- [subproject-rules.md](references/subproject-rules.md) — 源管理 / 隔离测试 runtime 包 / LF / Python 环境规避 / 路径不硬编码
- [plugin-authoring.md](references/plugin-authoring.md) — 插件包结构 / 字段 / 权限 / capabilities / BasePlugin / 页面路由 / i18n / 前端工具
- [packaging-testing-release.md](references/packaging-testing-release.md) — package.py / manifest / 字段一致性 / 隔离测试 / 运行时同步 / 发布收尾
- [known-framework-issues.md](references/known-framework-issues.md) — 框架已知缺陷避坑清单（已修复/未修复）+ 协调清单格式
- [assets/plugin-skeleton/](assets/plugin-skeleton/) — 最小可运行插件骨架（plugin.json + 主 py + index.html）
- [scripts/validate_plugin.py](scripts/validate_plugin.py) — 字段一致性/LF/pycache 校验器
- [scripts/pack_plugin.sh](scripts/pack_plugin.sh) — 系统 Python + 清 PYTHON* 打包封装
