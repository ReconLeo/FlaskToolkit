# FlaskToolkit

<p align="center">
  <img src="https://github.com/ReconLeo/FlaskToolkit/actions/workflows/ci.yml/badge.svg" alt="CI">
  <img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
  <img src="https://img.shields.io/badge/version-4.19.0-blue" alt="Version">
</p>

> 一个基于 Flask 的插件化**框架**：把散落的 Python 插件与纯前端工具装进统一的运行时，
> 动态安装、热重载、权限可控。自己写的、自己维护的、只跑在本地——不依赖云、不上传数据。
>
> **English**：[English](README.md) · **中文**：本页

## 为什么会有 FlaskToolkit（作者自述）

我写过很多"小玩意儿"：签到脚本、定时任务、文件处理、图表页……大多是 Python 写的，其中不少是 Flask 前后端一体的页面，也有不少是纯前端的 HTML。它们各自都好用，但都散落在各个文件夹里——每次想加个新功能，就得把登录鉴权、上传下载、页面骨架、定时任务这些轮子重新造一遍。

更让我在意的是：越来越多本该轻巧的事情，被搬到了网上——离线就不能用，还悄悄收集我的数据。我不想为了一个内部小工具去注册账号、接受隐私政策。我想要的，是跑在自己电脑上（顶多局域网里几个人能用）的小程序。

矛盾的爆发点，是我自己开发的 **Kaleido 题库系统**：一个单文件 Flask 应用，长到了 3600 多行，几十个 API 路由堆在一起——加一个功能，就得把登录鉴权、上传下载、页面骨架、定时任务全部重新过一遍。之前积累的所有摩擦，在这里彻底爆发；而 FlaskToolkit 里很多设计理念，正是 Kaleido 血脉的延续——面向权限设计 API、数据完整性校验、工具打包即点即用。后来 Kaleido 也整体迁到了这个框架上，拆成三个后端插件加一个打包的前端工具，成了这套设计第一个真正的实战检验。它同样开源：[github.com/ReconLeo/Kaleido](https://github.com/ReconLeo/Kaleido)。

于是就有了 FlaskToolkit：一个插件化**框架**——而不是又一个重复造轮子的工具站。它把我这些"自留地"小程序，连同各自的能力，装进一套可复用、可扩展的"地基"里。

它慢慢长成了现在的样子——几处代表性的亮点：

- **插件生态**：从单文件插件长成 **.zip 插件包**（模板 + 静态资源，安装即用）；纯前端 HTML 工具是一等公民；大插件可拆成多模板 + 辅助模块 + 静态资源，自带子页面。
- **权限与纵深防御**：统一三层权限（public/user/admin）、可选鉴权、审计日志、热重载；分层防护——**AST 静态扫描 → 能力声明交叉校验 → 运行时审计钩子**；登录失败锁定；可选 HTTPS。
- **统一文件传输**：全局上传上限 + 保存前预检、中文文件名下载（RFC 5987）、下载统计与 Range 断点续传，以及同步持久化上传助手（`save_uploads`：净化 + 去重 + 大小/配额预检一次完成）。
- **数据配额体系**：单插件配额 → 声明式 storage:limit → **全局总量上限 + 后台空间管理**。
- **国际化**：轻量 JSON 语言包（内置 zh-CN + en，可扩展）、模板/后端/前端统一 t()、每个页面都可切换语言 + 翻译工具。
- **低门槛上手**：首次运行向导 + 强制改密、邀请码自助注册、带权限标注的插件 API 文档页、单插件空间清理、可选 pip_dependencies 优雅降级。
- **安全传输**：自签名 HTTPS + 自动 **HTTP→HTTPS 308 跳转** + Secure Cookie 自动配置——旧 http:// 链接永不失效。
- **网络可达**：后台**网络与访问页**（分享链接 + 二维码、mDNS、IP 变化检测）+ 双击即用的桌面启动器（本机/局域网一键切换）。
- **移动端**：同 URL、服务端 UA 检测分发**独立移动端模板**——插件只需把同名模板放进 mobile/ 命名空间即接入。
- **统计洞察**：回答"到底发生了什么"的仪表盘——运行徽章、冷门插件提示、14 天请求趋势、错误 Top、按用户/按 IP 的访问画像。
- **Root 权限域与市场铺路**：插件可声明 framework 能力域三档（read/manage/core，core ≈ root），写核心全程审计；配套程序化插件管理服务层 + 插件级更新源。
- **事件总线与真依赖解析**：轻量进程内发布-订阅总线，插件间无需知道谁在监听即可通信；依赖解析支持版本约束 + 环检测。
- **运维与工具链**：版本检查 + 双后端更新、Factory Reset、备份/恢复、启动自检、完整性签名、插件脚手架与离线安装/卸载 CLI，以及 **46 脚本回归套件与 GitHub Actions CI**。

完整功能规格见[开发规范](documents/Flask-Plugin-Framework-Dev-Guide-v4.md)。

坦白说，这框架的目标不是"再造一个 Django"：它站在 Flask、APScheduler、Werkzeug 这些巨人的肩膀上，把我需要的那部分想法落了地。它的信任模型是朴素的——**安装插件即信任其作者**：插件与框架同进程、无沙箱隔离（详见开发规范 10.1）。v4.15 的 **framework:core** 权限是"安装即信任"之上的唯一显式升级——一个可审计的 **root** 授予，允许插件修改/删除框架自身核心文件，后台用醒目标识并全程审计，且置于 MIT 协议之下（作者对高风险操作造成的损失概不负责）。在"安装即信任"之上，框架又叠加了纵深防御——静态扫描、能力声明交叉校验、运行时审计钩子——并支持可选鉴权 / HTTPS 与数据配额管控，足以支撑**可信局域网 / 企业内网**的日常工具运行；若要对公网对抗性环境开放，仍需自行评估风险（插件仍无沙箱）。

我坚持的原则只有一个：**需求导向，怎么方便怎么来**。所以最终呈现给你的，是一个开箱即用、低门槛、能随手往里加工具、且数据始终在自己手里的工具箱。

## 它是什么

自托管的 Flask 插件化**框架**——把散落的 Python 脚本与纯前端 HTML 工具装进一套可复用、可扩展、跑在自己机器上的统一运行时：

- **插件是一等公民**：后端 **Python 插件**与**前端 HTML 工具包**运行时即可安装 / 更新 / 卸载 / 启用 / 禁用——单文件或携带模板、静态资源、甚至子页面的 .zip 插件包；文件监听**热重载**改完即生效，依赖解析器按版本约束排好加载顺序。
- **鉴权可选**：不装就是游客模式的个人工作台；装 auth 插件即有登录 + 三层权限（public/user/admin）控制与审计日志。
- **自带管理后台**：仪表盘 / 插件管理 / 日志 / 统计 / 网络与访问 / 系统重置，外加插件级与全局**数据配额**。
- **统一文件传输**：全局上传上限 + 保存前预检、中文文件名下载、下载统计与 Range 断点续传。
- **天生国际化**：JSON 语言包、模板/后端/前端统一 t()、每个页面都可切换语言。
- **安全护栏**：AST 静态扫描 → 能力声明交叉校验 → 运行时审计钩子、可选 HTTPS、登录失败锁定——足以支撑可信局域网与企业内网。
- **运维工具链**：备份 / 恢复、Factory Reset、启动自检、双后端（git / archive）更新、插件脚手架、离线安装/卸载。
- **想怎么跑怎么跑**：默认仅本机（127.0.0.1），`FLASKTOOLKIT_HOST=0.0.0.0` 即局域网共享；桌面启动器、mDNS、一键 HTTPS 让这一切变得无痛。

一句话：这是一个**插件化框架**——给你的本地小程序一个统一的家，以及一套不用重写的"地基"。

## 适合谁

**个人用户**——自己电脑上的私人工具箱：

- 默认仅本机访问（127.0.0.1），数据留在本地磁盘、不出本机；
- 鉴权可选：不装就是游客模式的个人工作台，想加登录保护再装 auth 即可；
- 不想碰命令行？运行 `python tools/desktop_launcher.py` 打开桌面启动器：启动/停止服务、切换仅本机/局域网共享、一键复制访问地址（二维码在后台**网络与访问**页）；
- 从官方示例起步，之后随时把自己的脚本作为插件丢进来；
- 大改动前养成习惯：`python tools/backup.py create` 先备份。

**局域网 / 小团队用户**——在可信网络内共享内部工具：

- 设置 `FLASKTOOLKIT_HOST=0.0.0.0`，同事即可通过局域网访问；
- 安装 auth 插件并分配账号——三层权限（public / user / admin）决定每个人能看什么、能改什么；
- 传输敏感内容时，用 `python tools/gen_cert.py` 生成 HTTPS 证书（或把服务放到反向代理后面）；
- 用 `python tools/update.py` 保持更新（开源仓库走 git 后端，离线内网走 archive 后端）；
- 记住信任模型：只安装你信任作者写的插件。

## 快速开始

```bash
pip install -r requirements.txt
python app.py

或者用桌面启动器（GUI）：`python tools/desktop_launcher.py`（启动/停止服务、选择仅本机或局域网共享、复制访问地址）。
```

浏览器打开 `http://127.0.0.1:5000` 即可（默认仅本机访问；如要局域网使用，设环境变量 `FLASKTOOLKIT_HOST=0.0.0.0`，见下方说明）。

首次运行建议安装内置 `auth` 插件以获得鉴权能力，默认管理员账号 `admin / admin123`（可在 `plugins/configs/auth.json` 修改）。

想马上感受"装插件"的乐趣？安装官方示例：

```bash
pip install -r requirements.txt -r requirements-dev.txt   # install_all.py 依赖 requests
python examples/install_all.py                            # 一键安装 8 个官方示例（7 后端插件 + 1 前端工具）
```

### 运行环境变量

| 变量 | 默认值 | 说明 |
|------|-------|------|
| `FLASKTOOLKIT_HOST` | `127.0.0.1` | 绑定地址；默认仅本机，局域网访问设 `0.0.0.0` |
| `FLASKTOOLKIT_PORT` | 自动探测 | 显式指定端口；被占用时自动回落 |
| `FLASKTOOLKIT_DEBUG` | 关闭 | 调试模式，生产环境请勿开启 |

## 官方示例

[`examples/`](examples/README.md) 随仓库分发一套可一键安装的示例，完整展示框架能力，也是新插件开发的起始模板：

| 示例 | 类型 | 一句话定位 | 能力标签 |
|------|------|-----------|---------|
| `hello_plugin` | 后端插件 | 脚手架模板：生命周期、权限、配置、自定义页 | 热重载 · 权限 · 生命周期 · 配置 |
| `scheduler_demo` | 后端插件 | APScheduler 定时任务（interval/cron）+ 事件总线 | 定时任务 · 事件总线 · 异步事件 |
| `async_file_demo` | 后端插件 | 异步任务 + 上传限制 + 声明式存储配额 | 异步 · 上传限制 · 存储配额 |
| `dependent_demo` | 后端插件 | 依赖解析 + 跨插件调用 + 跨插件事件订阅 | 依赖解析 · 跨插件调用 · 事件订阅 |
| `multitool_demo` | 后端插件 | 大插件形态：页面路由子页 + 辅助模块 + 静态资源 | 多模板 · 页面路由 · 静态资源 |
| `corp_tools` | 后端插件 | 企业内网工具箱：健康探测 + 权限导航 + 公告板 + i18n + 移动端模板 | 定时探测 · capabilities · i18n · 移动端模板 |
| `root_demo` | 后端插件 | Root 权限域：读写框架核心配置，全程审计 | Root 域 · framework:core · 审计 |
| `dashboard_demo` | 前端工具包 | 管理面板：调用后端 API + ECharts | 前端工具 · admin 权限 · ECharts |

详见 [examples/README.md](examples/README.md)。

## 文档

详细规格都在 [Flask 插件框架开发规范](documents/Flask-Plugin-Framework-Dev-Guide-v4.md)（插件开发、权限模型、前端工具规范、插件包格式、安全设计、运维工具）：

- [官方示例说明](examples/README.md)
- [版本演进记录](documents/Flask-Plugin-Framework-Changelog.md)
- [Flask 插件框架 Roadmap](documents/Flask-Plugin-Framework-Roadmap-v4.md)
- [版本收尾 checklist](documents/Release-Wrapup-Checklist.md)
- [GitHub Actions 上手与开源发布指南](documents/GitHub-Actions-Guide.md)
- [Enterprise Edition 交接与路线（v5.x）](documents/Enterprise-Edition-Handover-Roadmap.md)

## 测试与 CI

`tests/` 46 个回归测试脚本（隔离目录模式，不污染项目文件）；GitHub Actions 在 Python 3.10 / 3.11 / 3.12 上自动执行，覆盖权限、插件包 / 前端工具链路、完整性签名、卸载清单、Factory Reset、大插件多模板页面路由、文件传输（上传限制 / 中文名下载 / Range）、插件静态安全扫描、能力声明交叉校验、运行时审计钩子、i18n 语言框架、插件数据配额、事件总线与依赖解析、设备检测与移动端模板分发、插件脚手架与离线安装/卸载 CLI、单插件空间清理、运维工具等。

<details>
<summary>展开：46 个测试脚本</summary>

```bash
cd FlaskToolkit
python tests/test_permission.py            # 权限体系 20 项
python tests/test_stage2.py                # 安全加固回归 19 项
python tests/test_zip_slip.py              # 插件包 zip slip 19 项
python tests/test_pack_meta.py             # 插件包描述一致性 23 项
python tests/test_reload_race.py           # 热加载重载竞态 1 项（20 轮）
python tests/test_meta_e2e.py              # 插件包元信息端到端 11 项
python tests/test_frontend_zip_slip.py     # 前端工具 zip slip 21 项
python tests/test_frontend_chain.py        # 前端工具链路端到端 23 项
python tests/test_admin_api.py             # 管理端 API 69 项
python tests/test_factory_reset.py         # Factory Reset 范围 39 项
python tests/test_error_pages.py           # 错误码页面 12 项
python tests/test_package_sign.py          # 完整性校验/签名 25 项
python tests/test_plugin_cleanup.py        # 插件卸载 installed_files 清单 23 项
python tests/test_frontend_permission.py   # 前端工具访问控制 25 项
python tests/test_tools_ops.py             # 运维工具 backup/reset/config 19 项
python tests/test_page_router.py           # 大插件多模板页面路由 + 纯 API 无 name 插件调试页回归 21 项
python tests/test_framework_fixes.py       # 框架小修复：public_page 豁免 + CSRF 单值注入 12 项
python tests/test_file_transfer.py         # 文件传输：全局 413 / 插件级与 route 级上传上限 / 中文名下载 / 下载统计 / Range / on_ready 顺序 12 项
python tests/test_plugin_uploads.py    # 同步持久化上传助手（v4.18）：净化/去重/大小+配额预检/落盘 21 项
python tests/test_security.py              # 系统安全：安全响应头 / Cookie 加固 / 空闲超时 / 登录锁定与手动解封 45 项
python tests/test_plugin_scan.py           # 插件静态扫描（v4.3.1）：危险导入/调用/混淆/网络文件触点 35 项
python tests/test_capabilities.py          # 插件能力声明（v4.3.2）：解析/匹配/交叉校验/运行时授权 70 项
python tests/test_root_domain.py            # Root 域与市场铺路（v4.15）：framework 三档 / 插件管理服务层 / 插件级更新源 18 项
python tests/test_framework_manifest.py     # 框架目录清单（v4.15.1）：核心/用户数据单一清单 + Root 域路径判定 54 项
python tests/test_root_demo.py              # 示例插件 root_demo（v4.15.1）：framework:core Root 读写 + 对照拒绝 19 项
python tests/test_audit_hook.py            # 运行时审计钩子（v4.4.0）：事件映射/栈定位/observe/enforce 38 项
python tests/test_update_checker.py     # 版本检查推送（v4.8.0）：版本比较/数据源缓存 TTL/archive 校验链/zip slip 防护/自更新签名验签 50 项
python tests/test_plugin_updates.py    # 插件级更新源签名（v4.15/v4.17.1）：有效签名通过/篡改·无签名拒绝 8 项
python tests/test_release_sign.py      # 发布签名联动（v4.17.1）：release --sign 产出可被 update_checker 验证 5 项
python tests/test_src_layout.py        # package.py 源码布局自动映射（v4.17.2）：<name>.json+frontend/ → plugin.json+templates/static 16 项
python tests/test_i18n.py                  # i18n（v4.9.0）：语言包/查找链/语言解析/切换路由/模板渲染 29 项
python tests/test_data_limit.py            # 插件数据配额（v4.9.0-4.9.2）：路径判定/用量统计/storage:limit 声明/写目录作用域/上传预检/全局总量/TTL/禁用 32 项
python tests/test_setup.py               # 首次运行向导 + 强制改密（v4.10 M4）17 项
python tests/test_register.py             # 邀请码自助注册 + 审核（v4.10 M5）25 项
python tests/test_scaffold_tools.py       # 脚手架 + 离线安装/卸载闭环（v4.10 M6）53 项
python tests/test_network.py              # 网络与访问（v4.11）+ 308 跳转/Secure 判定（v4.12）41 项
python tests/test_mdns.py                 # mDNS 服务注册（v4.11，可选 zeroconf）22 项
python tests/test_ip_watcher.py           # IP 变化检测（v4.11）15 项
python tests/test_desktop_launcher.py     # 桌面启动器（v4.11）+ HTTPS 复选框（v4.12）36 项
python tests/test_stats.py                  # 数据统计洞察（v4.14）：时间桶 + 访问画像双维模型 / dashboard 总览化 / 14 天趋势与错误 Top 55 项
python tests/test_selfcheck.py              # 启动完整性自检（v4.15）：CORE_FILES 完整性 / 时区探测 / 完整自检 14 项
python tests/test_events.py                 # 事件总线（v4.16）：priority / once / off / weakref 清理 / 绑定方法强引用 / async 非阻塞 / 异常隔离 / 内置事件 11 项
python tests/test_dependency.py             # 依赖解析（v4.16）：dep_spec 解析 / semver 含预发布 / Kahn 拓扑 / 环 / 缺失排除 11 项
python tests/test_plugin_events.py          # BasePlugin 事件集成 + 示例演示（v4.16）：scheduler_demo 事件与手动触发 / dependent_demo 跨插件订阅 28 项
python tests/test_device.py                 # 设备检测 + 移动端模板分发（v4.17）：UA 分类 / 配置开关 / resolve_template / 公开页移动端模板 / BasePlugin 移动端命名空间 20 项
python tests/test_theme.py                 # 界面主题（v4.19）：主题注册白名单 / 非法回退 / Cookie 与用户配置优先级 / auto 深浅解析 / 后台+公开页深色变量 / plugin_default 移动端适配 10 项
# 合计 46 个回归脚本
```

</details>

## 版本状态

- **Community Edition（v4.x）**：功能开发持续进行，但架构规模有意识控制——专注小型局域网/个人用户场景，我们定期维护与发布（46 脚本回归套件 + CI）。
- **Enterprise Edition（v5.x）**：规划承载远期路线（权限模型细化、进程级沙箱、CSP 收紧、企业身份对接等）。因当前小团队开发能力有限，公开寻求接手者——详见 [Enterprise Edition 交接与路线](documents/Enterprise-Edition-Handover-Roadmap.md)。

## 已知局限

- **安全模型为"安装插件即信任其作者"**：插件与框架同进程运行、无沙箱隔离，可访问框架全部文件系统与网络权限；请只安装可信来源的插件。框架提供的静态扫描 / 能力声明 / 运行时审计是**降低风险的手段**，而非绝对隔离（详见开发规范 10.1）。
- 纵深防御下的建议使用范围：**本机或可信局域网 / 企业内网**（配合 `auth` 鉴权、按需启用 `PLUGIN_SCAN_MODE=enforce` 与 `AUDIT_HOOK_MODE=enforce`、HTTPS 可参考 `tools/gen_cert.py`）。
- 未针对公网对抗性环境加固，**不建议直接暴露到公网**；如需公网访问请自行叠加网关/代理层并评估风险。
- 局域网使用可设 `FLASKTOOLKIT_HOST=0.0.0.0`，请配合 `auth` 鉴权并自行评估风险。

## 许可与贡献

MIT License · 贡献指南见 [CONTRIBUTING.md](CONTRIBUTING.md) · 开发过程中使用了 AI 辅助编程，约定见下文声明。

### 人工智能辅助开发声明

本项目在开发过程中使用了 AI 辅助编程工具，包括但不限于：代码生成与重构、代码审查、测试用例编写、文档撰写。所有 AI 辅助生成或修改的内容，均已由开发者人工审查，并通过项目自身的回归测试套件（`tests/`，46 脚本）与启动完整性自检验证后才会合入。

对贡献者的透明性约定：

- 使用 AI 辅助工具是被允许的，但请对提交代码的**正确性、安全性、合规性**负全责。
- AI 生成的代码必须通过项目的回归测试与代码审查（流程见 `CONTRIBUTING.md`）。
- 若 PR 中大量使用 AI 生成内容，建议在 PR 描述中注明，便于维护者审阅。

## Star History

用 [Star History](https://www.star-history.com/?repos=ReconLeo%2FFlaskToolkit&type=date&legend=top-left) 记录本项目的成长历程。

<a href="https://www.star-history.com/?repos=ReconLeo%2FFlaskToolkit&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=ReconLeo/FlaskToolkit&type=date&theme=dark&legend=top-left&sealed_token=6DvZLa9sIvE1KVbLXbIdgQXFE-1hZ_BUK3nyhvtBdgg9TJIBWUD7X5e7VJa30UFnoIUGHciUofZ_Uu8rRfwUbJI_JFPNcma79J0rlrHUOPVqSr4u_4KItnn5bQPeSiWWr2kC6WYkRO63hCndr-wiCz8ie9PIvzXqZiX21cg8T1-Z9PzDSAoMzqFROHAP" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=ReconLeo/FlaskToolkit&type=date&legend=top-left&sealed_token=6DvZLa9sIvE1KVbLXbIdgQXFE-1hZ_BUK3nyhvtBdgg9TJIBWUD7X5e7VJa30UFnoIUGHciUofZ_Uu8rRfwUbJI_JFPNcma79J0rlrHUOPVqSr4u_4KItnn5bQPeSiWWr2kC6WYkRO63hCndr-wiCz8ie9PIvzXqZiX21cg8T1-Z9PzDSAoMzqFROHAP" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=ReconLeo/FlaskToolkit&type=date&legend=top-left&sealed_token=6DvZLa9sIvE1KVbLXbIdgQXFE-1hZ_BUK3nyhvtBdgg9TJIBWUD7X5e7VJa30UFnoIUGHciUofZ_Uu8rRfwUbJI_JFPNcma79J0rlrHUOPVqSr4u_4KItnn5bQPeSiWWr2kC6WYkRO63hCndr-wiCz8ie9PIvzXqZiX21cg8T1-Z9PzDSAoMzqFROHAP" />
 </picture>
</a>
