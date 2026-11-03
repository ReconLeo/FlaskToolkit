# FlaskToolkit 开发 AgentSkills

本目录收录开发 FlaskToolkit 时使用的 AgentSkills（[AgentSkills](https://github.com/anthropics/skills) 兼容格式：一个目录一个技能，入口为 `SKILL.md`，详细规则放 `references/`，可复用资产放 `assets/` / `scripts/`）。

| 技能 | 适用场景 |
| --- | --- |
| [`flasktoolkit-framework-dev/`](flasktoolkit-framework-dev/) | 开发/修改/回归/打包/发布 **主框架源码**（`core/`、`routes/`、`app.py`、`tools/`、示例插件、i18n、隔离副本开发、版本收尾） |
| [`flasktoolkit-subproject-dev/`](flasktoolkit-subproject-dev/) | 把独立工具开发成 **子项目插件**（后端 Python 插件 / 前端 HTML 工具包）：脚手架、字段一致性、打包、基于 release runtime 包的隔离测试、运行时同步与发布 |

## 通用性约定（重要）

这两个技能**刻意不含任何机器专属信息**，可直接复用到别人的开发机：

- 所有路径由**运行时参数/环境变量**提供，不硬编码：`FTK_FRAMEWORK_PATH`（框架根）、`FTK_RUNTIME_URL`（release runtime 包直链）、`FTK_GH_PATH`（GitHub CLI）、`SYSTEM_PYTHON`（干净解释器）。
- 不假定某个 Python 解释器路径、某个 IDE 或某个环境管理器。
- 与「某台机器特有的环境陷阱」相关的内容**单独归档**在 [`DEV-ENVIRONMENT-NOTES.md`](DEV-ENVIRONMENT-NOTES.md)：它是一份实例记录（作者本机），**不是技能的依赖**，其它机器遇到类似症状时按技能内 `references/local-env.md` 的通用三步定位法自查即可。

## 如何使用

- **支持 AgentSkills 的编码 agent**：把技能目录复制/软链到该 agent 的技能目录（例如 `~/.dsh/skills/`、`~/.claude/skills/` 等）后重启会话即可被发现。
- **手动参考**：`SKILL.md` 是入口（工作流与硬约束），`references/*.md` 按需查阅；两个技能内的 `references/` 与框架 `documents/` 下的权威文档（`Flask-Plugin-Framework-Dev-Guide-v4.md`、`Release-Wrapup-Checklist.md`、`Flask-Plugin-Framework-Changelog.md`）配合使用——技能只承载程序性知识，规格以仓库文档为准。
- 技能里引用的 `tools/*.py`、`tests/`、`examples/` 均指**框架根下的真实文件**，请把 `FTK_FRAMEWORK_PATH` 指向框架根后再执行其中的命令。

## 维护约定

- 技能只写「怎么做」的程序性知识，不复制框架文档正文，避免与仓库文档双份漂移。
- 修改技能后自检：不出现绝对路径 / 机器名 / 个人环境名；命令里的路径一律参数化。
- 新增框架能力导致技能过时时，先更新技能，再回来同步本节表格。
