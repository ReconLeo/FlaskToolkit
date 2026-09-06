# FlaskToolkit 版本演进记录

> 本文档完整记录 FlaskToolkit 的来龙去脉：从 Kaleido 题库系统的灵感，到 v4.1 的体系化落地，再到 v4.9.x 的持续演进与发布。
> 定位约定：README = 项目门面（精简），开发规范 = 权威规格，**本文档 = 版本特性与演进史（来龙去脉）**。

## 1. 项目起源：Kaleido → FlaskToolkit

FlaskToolkit 的直接灵感来自作者自己开发的 **Kaleido 题库系统**。

Kaleido 最初是一个独立的单文件 Flask 应用（`kaleido-app.py`，约 3600 行）：题库管理（学科/题库 CRUD、文件校验、版本迁移、错题回顾）、聚合搜索、RSA+AES 签名与加解密——几十个 API 路由全部堆在一个文件里。随着功能增多，**API 维护成本急剧上升**：加一个功能要同时改登录鉴权、上传下载、页面骨架、定时任务，处处小心翼翼。

正是这种"API 太多不好维护"的切肤之痛，直接驱动了作者开发本框架：**把通用运行时（鉴权、上传/下载、插件生命周期、权限、审计）抽成地基，让每个小工具只负责自己的页面和逻辑**。因此可以说，Kaleido 是矛盾的爆发点，FlaskToolkit 在爆发中诞生——**框架里的许多设计理念与 Kaleido 一脉相承**（面向权限设计 API、数据完整性校验、工具打包即点即用）。

这个设计最终被 Kaleido 自身的迁移验证：Kaleido 按功能拆成 3 个后端插件（`kaleido_qbank` 题库 / `kaleido_search` 聚合搜索 / `kaleido_crypto` 签名加解密）+ 1 个打包的前端工具，全部跑在 FlaskToolkit 内，读操作 public、写操作 admin 的权限矩阵由框架统一执行。

Kaleido 同样开源（自托管题库系统）：[github.com/ReconLeo/Kaleido](https://github.com/ReconLeo/Kaleido)。

## 2. 版本线总览

| 版本 | 日期 | 主题 | 关键 commit / tag |
|------|------|------|-------------------|
| 酝酿期 | 2026-08-22 ~ 08-24 | 架构审查与三阶段重构、插件包机制、管理后台、P0/P1/P2 冲刺 | （并入 v4.1 首个提交） |
| **v4.1** | 2026-08-24 | 插件化全栈工具集定型（git 仓库起点，含 CI 与开发运维工具） | `13819f6` |
| v4.2.0 | 2026-08-25 | 大插件多模板页面路由（版本门槛化） | `0057e98` |
| v4.2.1 | 2026-08-26 | public_page 豁免 + CSRF 单值注入 | `c1ad373` |
| v4.2.2 | 2026-09-02 | 文件传输强化（统一上传限制/中文名下载/Range/on_ready） | `4d7d602` |
| v4.3.0 | 2026-09-03 | 系统安全强化 P0（响应头/会话加固/登录锁定） | `f71b000` |
| v4.3.1 | 2026-09-03 | 插件静态扫描 + 配置预设（P1 阶段一） | `20763b4` |
| v4.3.2 | 2026-09-03 | 插件能力声明模型（P1 阶段二） | `ec7faa0` |
| v4.4.0 | 2026-09-03 | 运行时审计钩子（P1 阶段三，安全强化收官） | `c707c46` |
| v4.5.0 | 2026-09-03 | HTTPS 支持 + 数据路径迁移 + 检修收尾 | `b76c832` |
| v4.5.1 | 2026-09-03 | 登录锁定手动解封 | `f88fafe` |
| v4.6.0 | 2026-09-04 | 审计归因两缺陷修复 + strict 预设系统验证 | `a0689ff` + `c244585` |
| v4.7.0 | 2026-09-04 | 装饰性更新（项目宣传横幅 / 系统名个性化） | `8f2af0c` |
| **v4.8.0** | 2026-09-05 | 企业环境优化：版本检查推送 + 双后端更新；**首个分割 Release** | `a582945` + `4fc9325`，tag `v4.8.0` |
| v4.9.0 | 2026-09-05 | i18n 可扩展语言框架 + 插件数据配额 | `b1cf31d` |
| v4.9.1 | 2026-09-05 | 配额声明模型（storage:limit）+ 示例多语言 | `69c9ceb` |
| **v4.9.2** | 2026-09-05/06 | CI 三问题修复 + 全局总量配额 + 后台空间管理 | `fb7aa5b` + `18ff7ec`，tag `v4.9.2` |
| 补丁覆盖 | 2026-09-06 | tools 运维工具适配 v4.9 结构 + v4.9.2 覆盖发布 | `73c6a9f` `ee3e23d` `612c565` |
| **v4.11.0** | 2026-09-06 | Reachability 网络可达：地址中心（core/network.py）+ mDNS 服务注册（core/mdns.py 可选 zeroconf）+ 后台网络与访问页（二维码/共享/mDNS/IP 检测）+ 启动横幅播报 + IP 变化检测（core/ip_watcher.py）+ 桌面启动器（tools/desktop_launcher.py） | `e16e67b`（M1-M5）`4a76811`（文档），tag `v4.11.0` |
| **v4.10.0** | 2026-09-06 | Accessibility 能力可达性：pip 依赖独立声明 + 能力清单确认 + 调试页权限修正/API 文档增强 + 首次运行向导/强制改密 + 邀请码自助注册 + 脚手架/离线安装卸载 + 单插件空间清理 | `e26b25e`（M4）`2ecb8b7`（M5）`941ea66`（airdrop 移交）`32aa2ce`（M6）`9d3aaf4`（M6-Extra）`699fae0`（前端清理），tag `v4.10.0` |

## 3. 版本详情

### 3.1 酝酿期（2026-08-22 ~ 08-24，并入 v4.1 首个提交）

**架构审查与三阶段重构（2026-08-22）**
- 全量架构审查：定位致命漏洞 / 逻辑 bug / 架构反模式，输出 P0/P1/P2 修复优先级。
- 三阶段重构：阶段一（权限体系 + 鉴权修复）→ 阶段二（安全加固 A/B/C/D）→ 阶段三（架构拆分 Step1-6）。
- 代码结构定型：`app.py` 纯入口（约 150 行）、`global_var.py` 纯常量、`core/` 服务层、`routes/` 路由层、`plugins/` 插件目录；核心依赖 Flask / watchdog / APScheduler / flask-cors / importlib.metadata。

**插件包机制（2026-08-23）**
- 后端插件上传从单 `.py` 升级为**插件包（.zip）**：`plugin.json` 描述 + 主 `.py` + 可选 `templates/static`；`require_framework_version` 最低框架版本声明（parse + load 双校验）；内置插件 `auth` / `user_manage` 受保护。
- **卸载 installed_files 清单**：描述文件落盘全量清单，卸载/更新按清单精确清理，越界路径安全跳过。

**管理后台与配套（2026-08-23）**
- 管理后台五页面（dashboard / plugins / logs / stats / system），统一基模板 + `@admin_api` 权限保护。
- 六个统一风格错误码页（400/401/403/404/405/500）。
- Factory Reset（`core/factory_reset.py`）：部分范围（plugins/frontend_tools/stats_logs/sessions/temp）+ 全部（含内置插件配置还原）；**设计上不自动备份**（恢复初始状态是意图，仅弹窗提示先手动备份）。
- 修复 get_logs 日志读取、stats 补字段、user_manage HttpOnly token 死循环等一批框架 bug。

**稳定版冲刺 P0/P1（2026-08-23）**
- P0-1 上传大小限制（流式预检 413）；P0-2 信任模型文档化（插件即代码、无沙箱、安装即信任作者）；P0-3 Factory Reset 自动备份搁置（决策）。
- P1-1 requirements 版本锁定（Flask 3.1.3 等）+ requirements-dev.txt；P1-2 测试套件补全（+4 脚本 93 项，共 11 脚本 200 项）。
- Roadmap v4.1 文档落地（P0/P1/P2 分级 + 状态表）。

**P2 落地（2026-08-23）**
- P2-1 上传体验（前置校验/进度条）；P2-2 审计日志（JSONL + 后台查看）；P2-3 插件溯源（source/install_time/history）；P2-4 完整性校验 + RSA 签名（manifest 哈希清单 + `tools/package.py`，`PACKAGE_INTEGRITY_MODE`）。

### 3.2 v4.1（2026-08-24，`13819f6`）

git 仓库起点，此时已包含：插件包机制、管理后台、Factory Reset、前端工具（permission 三层访问控制，`a270454`）、配置/打包/备份/重置四 CLI、启动自检、GitHub Actions CI（Python 3.10/3.11/3.12）与 MIT 开源配套（LICENSE/CONTRIBUTING/.gitignore/操作指南）。文档定位决策：README = 门面，开发规范 = 权威规格。

### 3.3 v4.2.0（2026-08-25，`0057e98`）

**大插件多模板页面路由**：页面路由 `page=True` + 模板命名空间（`templates/plugins/<name>/`）+ `render/render_index` 助手 + 旧式 `page()` 兼容；示例 `multitool_demo` 演示多模板 + 辅助 `.py` + 静态资源三要素。FRAMEWORK_VERSION 升至 4.2.0 使其成为可声明版本门槛。

### 3.4 v4.2.1（2026-08-26，`c1ad373`）

AirDrop 插件化改造中发现的框架修复合入：interceptor `/plugin/` 守卫支持插件级 `public_page=True` 豁免（公开型插件页面不再被强制跳登录）；`plugin_common.js` 移除手动 CSRF 头注入（消除与全局 XHR 拦截的双重注入 403）。

### 3.5 v4.2.2（2026-09-02，`4d7d602`）

**文件传输强化**：全局 `MAX_CONTENT_LENGTH` 100MB 兜底 + 统一 413；`save_uploaded_file` 保存前流式预检；route 级 `max_upload`（MB）可突破全局（AirDrop GB 级场景）；中文文件名 RFC 5987 下载 + 下载统计 + Range 断点续传；新增 `on_ready` 就绪钩子（所有插件加载后统一调用）。

### 3.6 v4.3.0 ~ v4.4.0（2026-09-03，P0 + P1 安全强化）

| 版本 | 内容 |
|------|------|
| v4.3.0 | **P0 系统安全强化**：安全响应头、Cookie 加固、空闲超时、登录失败锁定 |
| v4.3.1 | **P1-1 插件静态扫描**：AST 级风险扫描器（`core/plugin_scanner.py`）+ 配置预设（daily/strict/lan-open）+ `tools/scan.py` |
| v4.3.2 | **P1-2 能力声明模型**：插件声明 `capabilities`（filesystem/network/scheduler/storage），与扫描结果交叉校验 |
| v4.4.0 | **P1-3 运行时审计钩子**：`sys.addaudithook` 拦截（off/observe/enforce），按插件聚合归因 |

P1 安全强化至此全部完成，形成纵深防御：**静态扫描 → 能力交叉校验 → 运行时审计钩子**。回归 22 脚本 482 项。

### 3.7 v4.5.0 / v4.5.1（2026-09-03）

- **v4.5.0**：HTTPS 支持（`SSL_CERT_FILE/SSL_KEY_FILE` + `tools/gen_cert.py` 自签名证书，缺项回退 HTTP 告警）；`frontend_tools.json` 迁移至 `data/`（原子迁移旧文件）；auth 会话迁移至插件自属目录（`plugins/data/auth/`）；审计钩子框架路径过滤；selfcheck CORE_FILES 补全；示例检修。
- **v4.5.1**：登录锁定**手动解封**（auth `unlock_user` + user_manage 后台解封按钮 + 用户列表锁定状态展示）。

### 3.8 v4.6.0（2026-09-04，`a0689ff` + `c244585`）

**strict 预设系统验证 + 审计归因两缺陷修复**：D1-D8 八维度验证全通过（预设应用/启动自举/上传链路/运行时/登录会话/后台/全量回归/资源稳定）；修复 `_locate_plugin` 栈归因两缺陷（框架加载器帧误归因导致 enforce 下插件无法加载；插件包辅助模块误归因导致隐式豁免失效、异步落盘静默失败）；B4/B5 测试固化。**验证结论：strict 预设可直接用于可信局域网/企业内网（配合 HTTPS + auth）。**

### 3.9 v4.7.0（2026-09-04，`8f2af0c`）

**装饰性更新**：F2 项目宣传（PROJECT_NAME/AUTHOR/GITHUB/SLOGAN + 启动横幅 + 后台页眉链接 + 关于卡片）；F3 系统名个性化（`SYSTEM_NAME` / `SYSTEM_VERSION_LABEL` 配置项，登录页/首页/后台/错误页系统名变量化）。

### 3.10 v4.8.0（2026-09-05，`a582945` + `4fc9325`，tag `v4.8.0`）

**企业环境优化更新**：
- **F1 版本检查推送**：`core/update_checker.py`（`changelog.json` 数据源、24h TTL 缓存、可选签名校验）+ 管理后台版本卡片 + 启动横幅提示（仅展示引导，不做一键更新）。
- **F4 双后端更新机制**：`tools/update.py`（git 后端 fetch/stash/reset + archive 后端下载校验/备份/替换/自动回滚，`USER_DATA_PATHS` 用户数据清单单处定义，git/archive 共用）+ `tools/release.py` 发布工具链（版本同步、精简/全量/定制三档包、changelog 生成与签名）。
- **首个分割 Release**：Community v4.x 与 Enterprise v5.x 分界点（`documents/Enterprise-Edition-交接与路线.md`，Enterprise 公开寻求接手者）。

### 3.11 v4.9.0（2026-09-05，`b1cf31d`）

**i18n 可扩展语言框架 + 插件数据配额**：
- i18n：`core/i18n.py` 轻量语言模块（零第三方依赖）——`locales/<lang>.json` 中文原文即 key，**扩展语言 = 新增语言包文件即自动发现**；查找链：插件语言包 → 框架语言包 → 原文回退；模板/后端/前端（`window.T`）统一 `t()`；`LANGUAGE` 配置 + Cookie 用户级切换（白名单校验防路径注入）。
- 数据配额：`PLUGIN_DATA_LIMIT_MB`（默认 50MB）+ 审计钩子写事件强制（纵深防御第四层）。

### 3.12 v4.9.1（2026-09-05，`69c9ceb`）

**配额声明模型 + 示例多语言**：capabilities 新增 `storage` 域（`storage:limit:<size>` 插件声明式申请存储空间，覆盖全局默认）；配额作用目录推导（自属 data/temp + filesystem:write 声明路径，覆盖 AirDrop uploads/ 场景）；`core/quota.py` 上传预检（413 + 剩余空间）；示例 `async_file_demo` 声明配额 + `corp_tools` 演示插件多语言。

### 3.13 v4.9.2（2026-09-05/06，`fb7aa5b` + `18ff7ec`，tag `v4.9.2`）

**CI 三问题修复 + 全局总量配额 + 后台空间管理**：
- CI 三问题（GitHub Actions 3.10/3.11 失败、3.12 通过）：f-string 嵌套同引号（PEP 701 仅 3.12+）改单引号 + `ast.parse(feature_version=(3,10))` 语法体检入 checklist；上传临时目录模块级创建（test client 路径 FileNotFoundError）；Actions 升 Node 24（checkout/setup-python/upload-artifact v6）。
- **全局总量配额**：`PLUGIN_DATA_TOTAL_LIMIT_MB`（默认 0=无限制）——单插件限额 + 全局总量双层（enforce 拒绝 / observe 记录）。
- **后台插件空间管理**：`GET /api/admin/quota` + 系统页"插件空间"卡片（每插件配额/用量/剩余 + 全局总量行）。
- 回归 25 脚本 612 项；发布时 README 双版 Over time 段精简为主题里程碑（细节指向开发规范）。

### 3.14 补丁：tools 运维工具适配 + v4.9.2 覆盖发布（2026-09-06，`73c6a9f` `ee3e23d` `612c565`）

- **release.py**：精简运行包白名单补 `locales`（v4.9.0 i18n 语言包为运行必需，旧包缺失导致升级后界面翻译丢失）；`users/`（AI 助手本地数据）加入用户数据清单（发布包/框架备份均不携带）。
- **backup.py**：移除 `data/frontend_tools.json` 冗余条目（data 整目录已含）。
- **reset.py**：服务运行检测读取用户配置 `HOST/PORT`（替代硬编码 5000）。
- **update.py / release.py**：用法文档修正为位置子命令（`check`/`apply`/`rollback`、`bump`/`build`）。
- 全量回归 25 脚本 615 项；v4.9.2 Release 资产覆盖上传（新 sha256 `f232d501`）、changelog 同步、Release 描述 Upgrade hint 修正（locales 已内置）；README 双版 Why/What 精简更新 + 新增两类人群（个人/局域网）使用建议 + Kaleido 灵感故事。

## 4. 发布实践沉淀

- **changelog.json 是发布强制同步点**：`tools/release.py build` 会重写（latest_version/sha256/download_url/changes），须随 Release 一起 commit + push（v4.9.0/v4.9.1 曾漏同步，v4.9.2 补齐并固化）。
- **四端点同步**：`global_var.FRAMEWORK_VERSION` + `tests/test_admin_api.py` 断言 + README 双版徽章 + `SYSTEM_VERSION_LABEL`（release.py bump 自动同步三处 + 徽章）。
- **Release 完整流程**：release.py build（拿 sha256 + 写 changelog）→ git commit（README/changelog）→ git tag + push → gh release create 上传 zip + Release notes → 端到端验证（raw changelog.json 200 + zip 下载 sha256 比对）。
- **覆盖发布**：同版本号重新发布时，用 `gh release upload <tag> <zip> --clobber` 覆盖资产；Release 描述与 changelog sha256 必须同步更新，避免更新校验链断裂。
- **README 故事段维护**：保持精简（主题里程碑聚合），细节指向开发规范与本演进记录，避免随版本膨胀。
