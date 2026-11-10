---
name: flasktoolkit-framework-dev
description: 用于开发、修改、回归、打包与发布 FlaskToolkit Community 主框架源码。适用于 coding agent 需要操作 FlaskToolkit 主仓库时，包括：(1) 新增/修复框架核心模块（core/、routes/、app.py、tools/）、(2) 回归测试与 CI 同步（tests/、ci.yml）、(3) 示例插件开发/升级与打包、(4) i18n 文案与语言包同步、(5) 隔离框架副本内开发、(6) 版本发布收尾（版本号同步、runtime 打包、GitHub Release）。内含 Community 定位硬约束（企业级越界不实现）与路径不硬编码铁律。
disable-model-invocation: false
---

# FlaskToolkit Community 主框架开发

本技能为 coding agent 提供开发/维护 FlaskToolkit **Community 主框架**（仓库根即框架源码树）的程序性知识与工作流。技能采用「精简总览 + 分领域 references」结构：本文只承载硬约束与工作流入口，细节按需加载对应 reference 文件。

## 前置：路径不硬编码铁律

**本技能内所有路径（框架根、gh.exe、git、runtime zip 来源）均不硬编码，由 agent 首次使用时向用户采集并后续复用。** 命令统一使用占位符：

- `{FRAMEWORK_ROOT}` —— FlaskToolkit 主仓库根目录（含 `app.py`、`core/`、`tools/`、`documents/`）。所有相对路径基于它推算。
- `{GH_EXE}` —— GitHub CLI 可执行文件绝对路径（Git Bash PATH 通常不含，如 `D:\GitHub CLI\gh.exe`）。
- `{RUNTIME_URL}` / `{RUNTIME_ZIP}` —— 隔离副本使用的 runtime 包 URL / 本地 zip 路径。

首次使用先采集：`{FRAMEWORK_ROOT}`、`{GH_EXE}`、git 是否可用（`git --version`）、以及是否涉及隔离副本开发（见下）。**绝不自行猜测或硬编码这些路径。**

## Community 硬约束（每次改动前必读）

1. **Community 非功能冻结，而是架构规模有意识控制**：专注小型局域网/个人用户，持续迭代；企业级能力归 Enterprise（v5.x），由接手方主导。
2. **新功能范围判定**：贴合个人/局域网/插件开发友好 → 评估实现；企业级越界（深层安全 / 平台生态 / 企业部署）→ 引导 Enterprise 讨论，Community 不实现、不深化既有越界能力（仅做必要 bug 修复）。判定清单见 [community-boundaries.md](references/community-boundaries.md)。
3. **产品名称**：品牌名只能用 **FlaskToolkit**；界面/文档/词条中不得把 "Flask" 单独用作品牌（Flask 是 Pallets 的 BSD-3 项目）。技术性引用、文件名路径、Changelog 历史旧名可保留。
4. **发布门禁**：未过版本治理门禁、**未经用户明确指示**不得发布、不得打 tag、不得提升/改写版本号。详见 [release-workflow.md](references/release-workflow.md)。
5. **扫描门禁语义（v4.23.5 固化，改动前必读）**：不可约束 high（eval/exec/compile、pickle/marshal、混淆、动态导入、socket.bind/listen、syntax、subprocess…）**始终阻断**，`capabilities` 不能为其背书 —— `# scan:ignore`（行级知情声明）是唯一通路；可约束 high（rmtree 常量路径）按 `filesystem:write` 归因豁免；子进程另需 `process:exec[:<bin>]` 按可执行名（basename）归因，动态构造命令拒绝。判定只有一处：`core/plugin_scanner.evaluate_gate()`，不要在调用方复制分层逻辑。动态分析/签名者背书/管理员白名单属 Enterprise，Community 不实现。

## 核心工作流

按任务类型进入对应工作流。每个环节标注了应读取的 reference 文件（渐进式披露：只在需要时加载）。

### A. 主框架新功能 / 修复开发
1. **范围判定**：改动前先读 [community-boundaries.md](references/community-boundaries.md) 确认不越界。
2. **结构认知**：读 [repo-layout.md](references/repo-layout.md) 了解模块职责与 `core/framework_manifest.py` 清单登记要求（新增框架顶层内容必须登记 RUNTIME_*）。
3. **开发纪律**：读 [dev-conventions.md](references/dev-conventions.md) 了解行尾规则（LF/CRLF 分文件）、版本号五端点同步、文档双同步、changelog 同步。
4. **回归验证**：改完读 [testing.md](references/testing.md) 跑全量回归、ci.yml TESTS 同步、Python 3.10 体检。
5. **打包/发布**：读 [packaging.md](references/packaging.md) 与 [release-workflow.md](references/release-workflow.md)（仅在用户指示发布时）。

### B. 示例插件开发 / 升级
- 直接读 [example-plugins.md](references/example-plugins.md)：插件包标准结构、plugin.json 与类属性两处一致、require_framework_version、capabilities 匹配、manifest/README 同步、打包校验。
- 若涉及插件内 i18n 文案，同时读 [i18n.md](references/i18n.md)。

### C. i18n 文案 / 语言包同步
- 读 [i18n.md](references/i18n.md)：`locales/` 语言包、en.json 基准、`tools/i18n_status.py` / `tools/scan_missing_i18n.py` 校验、插件语言包 `self.t()`。

### D. 隔离框架副本内开发
- 用户要求「在框架副本内开发」时读 [framework-copy.md](references/framework-copy.md)：获取最新 runtime 的两种途径（GitHub release 下载 / 仓库 `releases/` 现成包 + 版本核查），副本验证后同步回主框架。

## references 索引（按需加载，勿一次全读）

| 文件 | 何时读取 |
|------|---------|
| [community-boundaries.md](references/community-boundaries.md) | 任何改动前判定范围；遇到企业级需求 |
| [repo-layout.md](references/repo-layout.md) | 摸清目录/模块职责；新增框架顶层文件 |
| [dev-conventions.md](references/dev-conventions.md) | 写代码/改文档前；涉及版本号、行尾 |
| [example-plugins.md](references/example-plugins.md) | 开发/升级 examples/plugins/ 下示例插件 |
| [i18n.md](references/i18n.md) | 涉及界面文案、语言包、插件多语言 |
| [testing.md](references/testing.md) | 改代码后回归；新增测试脚本 |
| [packaging.md](references/packaging.md) | 打插件包 / 构建 runtime 包 |
| [framework-copy.md](references/framework-copy.md) | 隔离副本内开发；获取 runtime |
| [release-workflow.md](references/release-workflow.md) | 版本发布收尾 |
| [local-env.md](references/local-env.md) | 回归/打包/启动服务出现「只在本机复现」的报错时：解释器隔离与环境体检（通用） |

## 权威文档（仓库内，勿在技能内整段拷贝）

- `documents/Flask-Plugin-Framework-Dev-Guide-v4.md` —— 开发规范权威规格（目录树/详细规范唯一出处）。
- `documents/Release-Wrapup-Checklist.md` —— 版本收尾 checklist 权威清单。
- `documents/Enterprise-Edition-Handover-Roadmap.md` —— Community/Enterprise 边界与交接。
- `README.md` + `README.zh-CN.md` —— 门面（亮点/断言数/徽章/示例表，双版同步）。
- `documents/Flask-Plugin-Framework-Changelog.md` —— 历史演进唯一出处。

> 本技能不含机器专属信息：框架根、GitHub CLI、解释器等路径一律由用户提供（见上文占位符）。
> 若你遇到「只在这台机器复现」的环境怪象，按 [local-env.md](references/local-env.md) 的通用三步定位法自查；
> 仓库 `skills/DEV-ENVIRONMENT-NOTES.md` 里有一份**实例记录**（非技能依赖，仅供对照）。
