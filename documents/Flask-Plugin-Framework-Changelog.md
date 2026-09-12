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
| **v4.10.0** | 2026-09-06 | Accessibility 能力可达性：pip 依赖独立声明 + 能力清单确认 + 调试页权限修正/API 文档增强 + 首次运行向导/强制改密 + 邀请码自助注册 + 脚手架/离线安装卸载 + 单插件空间清理 | `e26b25e`（M4）`2ecb8b7`（M5）`941ea66`（airdrop 移交）`32aa2ce`（M6）`9d3aaf4`（M6-Extra）`699fae0`（前端清理），tag `v4.10.0` |
| **v4.11.0** | 2026-09-06 | Reachability 网络可达：地址中心（core/network.py）+ mDNS 服务注册（core/mdns.py 可选 zeroconf）+ 后台网络与访问页（二维码/共享/mDNS/IP 检测）+ 启动横幅播报 + IP 变化检测（core/ip_watcher.py）+ 桌面启动器（tools/desktop_launcher.py） | `e16e67b`（M1-M5）`4a76811`（文档），tag `v4.11.0` |
| **v4.12.0** | 2026-09-06 | Secure 安全传输：HTTP→HTTPS 自动跳转（308 保留 POST）+ SESSION_COOKIE_SECURE 自动配置（None=自动）+ config.py SSL 配对提示/HTTPS 状态检查 + 桌面启动器 HTTPS 复选框与证书自动生成 + 反代支持归档（TRUST_PROXY_HEADERS / EXTERNAL_SCHEME / EXTERNAL_HOST / EXTERNAL_PORT） | `919cb0b` `d0ccec7`（阶段1-2）`2b3762c`（feat）`fbbc60a`（docs），tag `v4.12.0` |
| **v4.12.1** | 2026-09-06 | Secure 修复：P1 登录回归 F10（is_secure_cookie_mode 跟随 request.scheme）+ 压力与多机归因评估落地（test_server 脚手架 + 评估报告，R6 归因闭环） | `f8cfd21`（feat）`786ae5d`（docs），tag `v4.12.1` |
| **v4.12.2** | 2026-09-07 | 安全修复：上传临时文件防线——F6 失败分支统一清理（preview/confirm 失败残留）+ preview 文件 TTL 30min 防写盘累积 + F12 preview_id 路径穿越封堵（严格 uuid 格式校验）+ test_admin_api 62→69 项 | `84c17ed`，tag `v4.12.2` |
| **v4.13.0** | 2026-09-07 | Mobile & Tablet 移动端与平板适配：公开页面 + 后台管理页响应式翻修（mobile.css / admin-mobile.css 与原有样式分开创建）+ JS 增强层四件套（mobile.js：表格自动包裹/汉堡菜单/模态框全屏/toast 通栏）+ 14 框架模板幂等注入 + 五个示例插件各自 *_mobile.css | `ad2bf59`，tag `v4.13.0` |
| **v4.14.0** | 2026-09-07 | Statistics 数据统计洞察：时间桶 + 访问画像双维数据模型 / dashboard 总览化（徽章行 + 冷门提示 + 最近动态）/ 14 天趋势 + 错误 Top + 画像卡 / 跳转端口 POST body 消费修复 | `b2f56a3`，tag `v4.14.0` |
| **v4.15.0** | 2026-09-07 | Root 域与市场骨架：framework 能力域三档 read/manage/core + 程序化插件管理服务层（core/plugin_admin.py）+ 插件级更新源（plugin.json repo/update_feed + RSA 验签）+ 前端 Root·更新徽章 + selfcheck 时区探测（tzdata）+ requirements tzdata | `ef36a40`，tag `v4.15.0` |
| **v4.15.1** | 2026-09-07 | 框架目录清单统一（core/framework_manifest.py 单一清单驱动自检/升级/备份/重置/Root 判定）+ 示例插件 root_demo（framework:core Root 读写演示 + 对照拒绝），全量回归 37 脚本 987 项 | tag `v4.15.1` |
| **v4.15.2** | 2026-09-07 | 小修复：框架目录清单校正（documents 移出 CORE_DIRS）+ Statistics 模板翻译补全（en.json 114→239）+ test_i18n 覆盖断言（28→29 项） | tag `v4.15.2` |
| **v4.15.3** | 2026-09-07 | 小修复：剩余页面模板硬编码中文翻译补全（en.json→485）+ test_i18n 覆盖断言 | tag `v4.15.3` |
| **v4.15.4** | 2026-09-09 | 稳定版体验优化：各页面语言切换 + 翻译工具 i18n_status.py（__contributors）+ 健壮性修复（HTTP 跳转端口容错/统计孤儿清理/汉堡隐藏等），全量回归 37 脚本 988 项 | tag `v4.15.4` |
| **v4.16.0** | 2026-09-10 | 事件总线 + 插件真依赖解析：自研 core/events.py（发布-订阅 weakref 防泄漏 async 线程池）+ core/plugin_deps.py（版本约束 + Kahn 拓扑 + 环检测）+ BasePlugin 事件集成（on_event·emit_event·event_name·_cleanup_events）+ 卸载反向依赖检查 + scheduler_demo 1.2.0·dependent_demo 2.0.0 事件演示，全量回归 40 脚本 | tag `v4.16.0` |
| **v4.17.0** | 2026-09-10 | 移动端/桌面端页面分离：core/device.py（UA 检测 + resolve_template 分发）+ templates/mobile/ 独立模板 + mobile-app.css + BasePlugin 移动端能力（is_mobile_context·mobile_template·render 分发）+ corp_tools 1.1.0 移动端独立模板演示，test_device 20 项 | tag `v4.17.0` |
| **v4.17.1** | 2026-09-11 | 签名功能验证 + 修复自更新/插件更新源验签 bug（_verify_feed_signature 漏传 signature，配公钥后签名永远失败）：新增 test_plugin_updates(8)·test_release_sign(5)，扩展 test_package_sign(25)·test_update_checker(50)，全量回归 43 脚本 1143 项 | tag `v4.17.1` |
| **v4.17.2** | 2026-09-11 | AirDrop 框架协调 A+C 组：冲突报错附两处值 + 描述文件失效打标与后台徽章 + 源码布局自动映射（--src-layout）+ CRLF 规范提示，新增 test_src_layout(16)，全量回归 44 脚本 1161 项 | tag `v4.17.2` |
| **v4.18.0** | 2026-09-11 | B 组同步持久化上传助手：BasePlugin 新增 upload_dir + sanitize_filename + save_uploads（单/多文件·净化·去重·大小+配额双预检·直接落盘），AirDrop upload_files/get_safe_filename 迁移，新增 test_plugin_uploads(21)，全量回归 45 脚本 1182 项 | tag `v4.18.0` |
| **v4.19.0** | 2026-09-11 | 全量界面深色模式 + setup 双语并显：core/theme.py（auto/light/dark 注册表 + Cookie 与用户配置双存）+ theme.js（auto 解析与监听）+ main.css/error.css/admin 深色变量化 + 16 模板接入 + setup.html 双语主次切换，新增 test_theme(10)，全量回归 46 脚本 1194 项 | tag `v4.19.0` |
| **v4.19.1** | 2026-09-11 | 插件主题接入便利化（AirDrop 协调清单 6.7）：core/theme.py 新增 resolve_effective_theme（light/dark 实际值、auto/非法交前端）+ inject_i18n 注入 theme_effective 到所有模板 + 独立 static/css/theme.css（:root 语义变量 + dark 覆盖，main.css 改 @import）+ multitool_demo 1.1.0 模板主题三件套样板，test_theme 扩展 A4（11/11），端到端渲染验证 17/17 + migrate_legacy_config 同路径防误删修复（test_frontend_permission 25/25），全量回归 46 脚本 1195 项 | tag `v4.19.1` |
| **v4.19.2** | 2026-09-12 | 可扩展主题（themes/ 目录扫描，AirDrop 交接）：core/theme.py available_themes 扫描 THEMES_DIR（mtime 缓存，运行期生效）+ 新增 get_theme_css + /theme-static 路由 + theme.js KNOWN 动态化（data-themes + 自定义 CSS 按需加载/404 回退）+ 16 框架模板/4 插件样板加 data-themes + 切换器动态渲染 + 被删主题全链路兜底（后端回退 auto 不清 Cookie，前端 CSS 404 回退）+ 自带 sepia 示例；test_theme 11→25、前端 jsdom 11、端到端集成 21 | tag `v4.19.2` |
| **v4.20.0** | 2026-09-12 | 用户中心（审核符合 Community）：登录用户自助改昵称/改密码，用户名不可改；auth.py 新增 update_nickname + update_nickname_api（POST /api/auth/user/update-nickname）+ 独立页面 /user-center（interceptor 守卫，需登录）+ user_center.html/js + 后台/公开页导航入口 + 强制改密弹窗提示；新增 test_user_center 13 + jsdom 12 | tag `v4.20.0` |
| **v4.20.1** | 2026-09-12 | update_checker 修复：background_check 改 force=True（有缓存重启后仍重新远程获取），test_update_checker 50→52，全量 47 脚本 1224 项 | tag `v4.20.1` |

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
- **首个分割 Release**：Community v4.x 与 Enterprise v5.x 分界点（`documents/Enterprise-Edition-Handover-Roadmap.md`，Enterprise 公开寻求接手者）。

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

### 3.15 v4.10.0（2026-09-06，tag `v4.10.0`）

**Accessibility（能力可达性）**——让"该有的能力够得着"：对个人/局域网用户补齐首次使用、注册、脚手架、离线部署等关键路径（计划 6 模块，本批全部落地）。

- **M1 pip 依赖独立声明**：`dependencies` 语义收窄为**仅插件依赖**，新增 `pip_dependencies` 独立字段（plugin.json / 类属性 / AST 提取 / 描述一致性冲突与兜底）；用 `importlib.metadata` 检测第三方包，缺失时**仅跳过加载 + 告警**（附 `pip install` 命令，不自动安装）；老写法（3.x 在 dependencies 混写 pip 包）向后兼容按包检测 + 迁移告警。
- **M2 安装前能力清单确认**：上传两段式——`preview=1` 返回能力预览（依赖 / pip 依赖 / capabilities 声明 / 静态扫描摘要）+ `preview_id`，`confirm=1&preview_id` 才执行安装；修复 upload `finally` 清理误删 preview 文件的 bug。
- **M3 API 文档页增强（仅管理员）**：`build_api_info` 提升为共享函数（含 `permission` 权限层级标注）；新增 `/__plugin_api__/<name>` 直达调试页；调试页权限修正移入 `ADMIN_GUARD_PREFIXES`（游客 302 / 普通用户 403 / 管理员 200）。
- **M4 首次运行向导 + 强制改密**：`data/.setup_done` 向导标记 + `/setup` 路由（LANGUAGE 白名单写入）；首页未完成初始化重定向 `/setup`；auth 自助改密（校验旧密码 + 踢除其他会话），登录响应 `must_change_pwd`（默认密码仍为 admin123 时为 true），后台弹改密窗可暂缓但下次登录仍提醒。
- **M5 邀请码自助注册**：`ALLOW_REGISTER`（默认关）；一次性邀请码（FTK-XXXXXXXX-XXXX，`plugins/data/auth/invite_codes.json` 一次性消费）；用户 `status` pending/active——持码注册即 active 免审核，无码进 pending 待管理员审核（登录 403 拦截）；user_manage 新增待审列表/通过/拒绝/邀请码生成/复制注册链接/撤销 6 个管理 API。
- **M6 插件脚手架 + 离线安装**：`tools/scaffold.py` 生成 backend/frontend 标准骨架（产出可直接 `tools/package.py` 打包）；`tools/install_plugin.py` 不跑框架手动安装——backend（完整性校验 / 描述一致性 / 框架版本 / 静态扫描门禁 → 安全解压 + installed_files 落盘 → 缺失 pip 依赖提示）、frontend（config.json/入口 html 校验 → 注册）；同名拒绝 / `--update` 升级拒绝降级；`list` 离线查看；`--base` 指定框架根。
- **M6-Extra 离线卸载 + 单插件空间清理**：`cleanup_plugin_data(name, include_data)`——临时目录与全部数据（data/ + 临时 + capabilities `filesystem:write` 声明写目录，如 AirDrop `uploads/`，离线自动从描述文件解析）；后台 `POST /api/admin/plugins/<name>/purge-data`（scope=temp/all，含配额缓存失效）；`install_plugin.py uninstall --purge-data` 离线等价；`factory_reset` plugins 范围补漏——一并清理非内置插件数据目录（`plugins/data/<name>/`）。
- **M7 版本收尾**：修复 `tools/release.py` bump 锚点 bug（版本替换锚点误用新版本号，改为从 global_var 读当前版本）；精简运行包 `RUNTIME_TOP` 补 `tools/`（离线 CLI 面向使用者）；后台插件空间卡片补『清理临时/清理全部』（修复 loadQuota 既有 getCsrfToken 未定义 bug → `_getCsrfCookie()`）；locales/en.json 补 6 词条。
- **回归**：25 脚本 615 项 → **28 脚本 737 项**（新增 test_setup 17 / test_register 25 / test_scaffold_tools 53，多脚本扩充）；AirDrop 插件加载回归（8 项）移交 AirDrop 子项目维护，不入主仓库。

### 3.16 v4.11.0（2026-09-06，tag `v4.11.0`）

**Reachability（网络可达）**——承接 v4.10"用得上"的递进：解决"非固定 IP 每次都要重新发布访问链接"痛点，让普通用户"够得着"框架。

- **M1 地址中心（core/network.py，纯标准库）**：局域网 IP 发现（getaddrinfo + ipconfig / hostname -I + UDP 兜底，过滤 127./169.254./0.0.0.0 去重）、端口三级优先（运行时注册 > 环境变量 > 配置 > 5000）、访问地址组合去重、`is_https_enabled`/`get_scheme`/`get_access_urls`（mDNS 置顶、127 仅本机、0.0.0.0 全部可达）。
- **M2 mDNS 服务注册（core/mdns.py，可选依赖）**：`zeroconf` 缺失降级提示不影响启动（延续 v4.10 pip_dependencies"可选依赖增强"理念）；`_flasktoolkit._tcp.local.` 服务类型；ServiceInfo 构造兼容新版（addresses）/旧版（address）。
- **M3 后台『网络与访问』页**：`GET /api/admin/network` + `POST /api/admin/network/config`（白名单 HOST/MDNS_ENABLED/MDNS_HOSTNAME/IP_WATCH_INTERVAL，类型校验，审计日志）+ 页面（分享地址列表/复制/二维码 qrcodejs 离线/共享开关/mDNS 开关/IP 检测间隔/防火墙提示）；后台导航新增『🌐 网络与访问』。
- **M4 启动横幅播报 + IP 变化检测（core/ip_watcher.py）**：启动后注册真实端口并逐行播报访问地址；`check_once` 快照比较（首次不视为变化，变化记 last_change_ts/详情并日志 warning），`IP_WATCH_INTERVAL` 秒轮询（0=关闭）。
- **M5 桌面启动器（tools/desktop_launcher.py，tkinter）**：GUI 启动/停止服务、仅本机·局域网切换、地址列表/复制/打开浏览器、日志区；subprocess 解耦不 import 框架核心；`--smoke`/`--shared`/`--port` CLI；二维码需 qrcode + PIL 可选库（缺失仅隐藏二维码区）。
- **配置项新增**：`MDNS_ENABLED`（默认 false，需重启）、`MDNS_HOSTNAME`（默认 flasktoolkit）、`IP_WATCH_INTERVAL`（默认 30）。
- **回归**：28 脚本 737 项 → **32 脚本 779 项**（新增 network / mdns / ip_watcher / desktop_launcher 四脚本 + admin_api 网络用例扩充；2026-09-06 复核：本批最终项数 network 41 / admin_api 62，全仓实测 869）。

### 3.17 v4.12.0（2026-09-06，tag `v4.12.0`）

**Secure（安全传输）**——承接 v4.11 Reachability，补齐 HTTPS/反代部署链路（阶段 1-2 反代支持 + 本批四模块）；HTTPS 稳定性经五阶段评估（见 `documents/archive/HTTPS-RevProxy-Stability-Evaluation.md`）。

- **M1 HTTP→HTTPS 自动跳转**：`core/network.start_http_redirect`——直连 HTTPS 模式下主端口+1 起 **308** 跳转端口（保留 POST 方法与 body，Host 头兼容 IPv6，daemon 线程）；反向代理场景不启用（Nginx 负责）。
- **M2 SESSION_COOKIE_SECURE 自动配置**：默认 **None=自动**——`is_secure_cookie_mode()`：HTTPS 直连或 `EXTERNAL_SCHEME=https` 自动 True，纯 HTTP 局域网自动 False（防浏览器丢 Cookie）；true/false 可显式强制；auth 两处 set_cookie（token/csrf_token）统一接入。
- **M3 config.py 适配**：`set` 对 SSL_CERT_FILE/SSL_KEY_FILE 配对提示；`check` 新增 HTTPS 状态块（配对/文件存在/反代一致性提示）。
- **M4 桌面启动器 HTTPS**：`ensure_https_cert` 缺证书自动 subprocess 调 gen_cert.py 生成；GUI HTTPS 复选框（按现有配置预选）+ CLI `--https`；分享链接/横幅随 scheme 显示 https。
- **反代支持归档**：`TRUST_PROXY_HEADERS`（ProxyFix 信任 X-Forwarded-Proto/For/Host，恢复客户端 IP 归因）+ `EXTERNAL_SCHEME`/`EXTERNAL_HOST`/`EXTERNAL_PORT`（外部入口，分享地址/二维码/横幅置顶输出）+ `app.validate_ssl_cert`（PEM 可读/配对/有效期校验，启动失败友好退出）；mDNS 提示随 scheme 插值。
- **回归**：v4.11 收尾时 32 脚本 779 项；2026-09-06 全量实测复核 **32 脚本 869 项**（network 41 / mdns 22 / ip_watcher 15 / desktop_launcher 36 / admin_api 62——版本说明中的 779/807 系增量估算，以实测为准）；runtime 83 文件（sha256 `da9711c1...`），changelog 5 条。

### 3.18 v4.12.1（2026-09-06，tag `v4.12.1`）

**Secure 修复（登录回归）**——v4.12.0 的 `SESSION_COOKIE_SECURE` 自动判定被 `EXTERNAL_SCHEME` 全局联动：反代场景配置 `EXTERNAL_SCHEME=https` 后，内部 HTTP 直连（http://IP:端口）的登录 cookie 也被加 Secure，被浏览器/客户端按标准丢弃 → 登录后会话立即失效（登录态 API 全部 401）。压力与多机归因评估真机复现并修复。

- **`core/network.is_secure_cookie_mode()` 跟随请求实际协议**：自动模式优先取 `request.scheme`（反代场景经 ProxyFix 已反映外部协议 https、内部 http 直连为 http），不再受 `EXTERNAL_SCHEME` 联动；无请求上下文（启动横幅/CLI）回退 `get_scheme()`；显式 `true/false` 强制不受影响。test_network J 组 41/41 兼容。
- **压力与多机归因评估（阶段 3/4）落地**：`test_server/` 测试脚手架（android_client 三模式 + pc_stress + pc_collect + pc_audit_lookup + echo-upload 测试插件）入库；评估报告 `documents/archive/HTTPS-RevProxy-Stability-Evaluation-Stress.md`。
- **评估结论（部署建议）**：dev server 保持单线程（threaded 高并发会假死，F7）；大文件路由声明 `max_upload` 突破全局 100MB（F9）且反代需同步调大 Nginx `client_max_body_size`（F11）；多机 IP 归因直连/反代均验证正确（R6 闭环）。
- runtime 82 文件（sha256 `e855d173...`）。

### 3.19 v4.12.2（2026-09-07，tag `v4.12.2`）

**安全修复（上传临时文件防线）**——压力评估与侦查发现的上传链路安全收口，堵死"利用临时文件恶意写盘"与 preview_id 路径穿越。

- **F6 失败分支临时文件清理**：preview 校验失败 / confirm 安装失败分支此前不清理临时包，统一 `_safe_remove_temp()`（尽力删除 + 失败日志，不阻塞业务返回）。修复前反复"preview 失败/confirm 失败"可致 temp 无限累积写盘。
- **preview 文件 TTL 防护**：新增 `_cleanup_stale_preview_files(30min)`，每次上传接口入口顺带清理超 30 分钟未确认安装的 `preview_*.zip`——堵死"反复预览永不确认 → temp 无限累积"。
- **F12 preview_id 路径穿越（P1）**：校验从 `startswith('preview_')` 升级为严格格式 `^preview_[0-9a-f]{32}\.zip$`（uuid hex 精确匹配），`preview_../../xxx` 类穿越请求直接 400。
- **测试固化**：test_admin_api 62→69 项（无效 zip 普通/preview 上传后 temp 无残留、伪造 preview_id 400、路径穿越 400、过期 preview TTL 清理）。
- runtime 82 文件（sha256 `c7af3908...`）。

### 3.20 v4.13.0（2026-09-07，tag `v4.13.0`）

**Mobile & Tablet（移动端与平板适配）**——对框架前端页面与示例插件 CSS 的一次翻修，针对 Mobile / Tablets 设备的显示适配问题。核心原则：**新增 CSS 与原有 CSS 分开创建**（不修改原样式，便于回退与独立演进）。

- **公开页面移动端适配（static/css/mobile.css）**：与 main.css / error.css 分开维护。刘海屏安全区（viewport-fit=cover + env(safe-area-inset) 变量）、触摸目标 ≥44px、表格自动包裹滚动容器（.table-scroll）、首页导航汉堡菜单（.nav-toggle）、480px / 768px 响应式断点。
- **后台管理页移动端适配（static/css/admin-mobile.css）**：stats-grid 窄屏单列、模态框窄屏全屏化（.mobile-full）、toast 窄屏顶部通栏（body.mobile-narrow）、导航汉堡入口。
- **JS 增强层（static/js/mobile.js，IIFE 四件套）**：① wrapTables——表格自动包裹 .table-scroll 滚动容器（防重复：已包裹 / 嵌套表格 / 已在容器内跳过）；② setupBurger——首页导航注入 ☰ 汉堡按钮（点击切换 nav-open，点击外部关闭）；③ setupModalFull——≤480px 模态框加 .mobile-full 全屏类；④ setupToast——≤768px body 加 .mobile-narrow 通栏类。媒体查询变化自动重应用 + MutationObserver 兜底动态渲染的表格 / 弹窗。
- **模板注入（幂等）**：14 个框架模板（含 admin/base.html）统一追加 viewport-fit=cover、mobile.css / admin-mobile.css link 与 mobile.js script；示例插件 11 个模板引入各自 *_mobile.css。
- **示例插件移动端样式**：五个示例插件各自新增独立移动端 CSS——corp_tools（corp_mobile.css）、multitool_demo（demo_mobile.css）、hello_plugin（hello_mobile.css）、async_file_demo（async_mobile.css）、dashboard_demo 前端工具（dashboard_mobile.css）。
- **验证**：浏览器端到端（首页 / 登录 / 后台 dashboard / 统计页 / 系统管理页）确认资源注入与表格包裹 100% 生效、无 JS 错误；全量回归 **32 脚本 869 项 0 失败**。

### 3.21 v4.14.0（2026-09-07，tag `v4.14.0`）

**Statistics（数据统计洞察）**——从"后台管理到底要什么"出发的统计面板再规划。以"现在怎么样 / 谁在用什么 / 出了什么问题 / 我该做什么"四问为框架，把原本只有累计计数的统计升级为**时间序列 + 访问画像**双维数据模型，让管理员一眼看清运行状态与访问者构成。

- **数据模型（core/stats.py 重写）**：`daily_stats` 时间桶按天聚合（count/ok/4xx/5xx/ms，key 与 call_stats 一致 plugin:path / frontend:<tool>）；`access_profile` 访问画像双维——by_ip（count/last_seen/devices/by_user 关联）与 by_user（登录用户含管理员，游客仅记 IP）+ summary（total_visits/first_seen/last_seen）；30 天 TTL 可配置（STATS_RETENTION_DAYS，最小 7）。
- **埋点（routes/interceptor.py）**：before_request 记 `_ft_stats_t0` + 新增 after_request `global_stats_recorder`——API / 前端工具写桶+画像、/plugin/ 页面仅画像；**职责分离防双计数**（累计计数仍由原埋点维护）；401/403/404 计入 4xx 桶（before_request 阶段拿不到状态码是驱动 after_request 方案的主因）。
- **设备分类**：classify_device 纯 UA 关键字匹配（bot/tablet/mobile/desktop），无新增依赖。
- **dashboard 总览化**：运行徽章行（运行时长 / 协议 / 访问地址数 / IP 变化）+ 冷门插件提示（api_calls==0 且 enabled 非内置）+ 最近动态卡（audit 流 lines=8）；补上缺失的"网络与访问"页入口。
- **统计页增强**：14 天请求趋势（纯 SVG 柱状图，无前端依赖）+ 错误 Top 表（4xx/5xx TOP20）+ 访问画像卡（用户 Top10 / IP Top10 / 设备分布）。
- **框架漏洞修复（测试 J3 暴露）**：start_http_redirect 的 _jump 不消费请求体，单线程 HTTPServer 下 POST/PUT 带 body 在客户端发送阶段被 RST（WinError 10053）——按 Content-Length 消费 body 修复，跳转端口真实场景连接中止根治。
- **测试**：新增 tests/test_stats.py（55 项）；test_audit_hook E12 改为审计日志痕迹检查（框架常驻运行时真实 audit.log 存在性检查误报）；全量回归 **33 脚本 869 项 0 失败**。

### 3.22 v4.15.0（2026-09-07，tag `v4.15.0`）

**Root 权限域 + 第三方插件市场骨架**——Community 作为 Enterprise 的微缩版/试验台，为"插件能否操作框架核心、能否自建插件市场"铺路。

- **framework 能力域（core/capabilities.py）**：KNOWN_DOMAINS 新增 framework，三档 read/manage/core（core≈Linux root，隐含 manage/read，级别 3>2>1）；is_framework_core_path 判定框架核心路径（core/routes/templates 框架部分/app.py/global_var.py/data/user_config.json/plugins/status.json，豁免模板/插件数据目录）；filesystem:write 命中核心路径→errors 拒绝并提示改用 framework:core；cross_validate 中 framework:core 隐式覆盖核心路径写；check_filesystem 运行时核心写仅 framework:core 放行；新增 check_framework。
- **Root 审计与栈归因（core/audit_hook.py）**：allowed 核心路径写追加 root-access 审计事件；新增公共栈归因 locate_caller_plugin()（服务层权限判定，防插件冒用身份伪造）。
- **加载横幅（core/plugin_loader.py）**：加载 framework:core 插件打印醒目横幅；catalog 透传 repo/update_feed/capabilities。
- **程序化插件管理服务层（core/plugin_admin.py，新 288 行）**：require_manage（框架自身放行/插件须 framework:manage）、scan_gate、enable/disable/uninstall/purge_data/install_from_package/update_from_package；routes/admin 六个管理接口改薄壳调用服务层，为第三方插件市场提供程序化接入点。
- **插件级更新源（core/plugin_updates.py，新）**：plugin.json 声明 repo/update_feed，应用内 check-updates 触达各插件独立发布渠道——feed JSON {latest_version,published_at,download_url,sha256,changes[,signature]}、data/cache/plugin_updates.json 缓存（UPDATE_CHECK_INTERVAL 小时）、3s 超时静默、UPDATE_PUBLIC_KEY_PEM 强制 RSA 验签、版本比较；plugin_pack META_FIELDS 加 repo/update_feed（不进 COMPARE_FIELDS）。
- **前端（templates/admin/plugins.html）**：Root/Manage/Framework 徽章（⚠️ Root 红/manage 橙/read 蓝三色警示条）、插件更新徽章（⬆ vX 可更新）、检查更新按钮。
- **既有 bug 修复**：preview.capabilities 恒空（preview 分支 `from core.plugin_scanner import read_pack_capabilities` 实为 core.capabilities，ImportError 被 except 吞，v4.10 起恒空）→ 改顶层已导入函数。
- **启动自检增强（core/selfcheck.py）**：时区集中化（global_var.TIMEZONE，app.py BackgroundScheduler 改用它）——APScheduler 3.11 弃 pytz 改 zoneinfo，Windows 缺 tzdata 时顶层创建 scheduler 抛 ZoneInfoNotFoundError 使启动崩溃，selfcheck 新增时区探测在自检阶段致命报错并提示装 tzdata；CORE_FILES 补登记 core/plugin_admin.py、core/plugin_updates.py。
- **requirements.txt**：新增 tzdata==2026.3（Windows zoneinfo 必需，全新 Python 环境可复现）。
- **测试**：新增 tests/test_root_domain.py（18 项）+ tests/test_selfcheck.py（14 项）；test_capabilities 扩展 G 段 framework 域 13 项；修复 test_admin_api 版本期望；全量回归 **35 脚本 914 项 0 失败**。

### 3.23 v4.15.1（2026-09-07，tag `v4.15.1`）

**框架目录清单统一 + Root 演示示例 root_demo**——不再"各处硬编码核心/用户数据清单"，统一 `core/framework_manifest.py` 一次驱动自检/升级/备份/重置/Root 判定；新增 root_demo 示例插件端到端演示 `framework:core`（Root）能力。

- **框架目录清单统一（core/framework_manifest.py，单一事实来源）**：`CORE_FILES`（35 个核心文件，缺失致命）/ `CORE_DIRS`（6 个核心目录）/ `USER_DATA_PATHS`（10 条用户数据路径）/ `ROOT_RUNTIME_FILES` / 豁免与管辖规则 / `BACKUP_ITEMS`（备份范围派生）；判定函数 `is_user_data_path` / `is_core_file` / `is_framework_core_path`。模块为纯常量 + 纯函数，模块级不 import global_var（避免副作用），BASE_DIR 自推导。
- **各模块改读统一清单（删硬编码）**：core/selfcheck.py、tools/update.py、tools/backup.py、core/factory_reset.py、core/capabilities.py 均改 import manifest。**后续新增框架文件只需在 manifest 登记一处**，自检/升级/备份/重置/Root 判定全自动跟随。
- **示例插件 root_demo（官方 Root 域演示）**：plugin.json 声明 `framework:core` + `filesystem:read:data/`、require_framework_version=4.15.0。后端 `/overview`（框架版本/Root 级别/核心文件清单）、`/config`（读/写 data/user_config.json，Root 授权 + 审计 root-access）、`/demo-reject`（对照：仅 filesystem:write 写核心被拒）；页面模板 + 插件语言包。
- **测试**：新增 test_framework_manifest.py（54 项）+ test_root_demo.py（19 项）；适配 test_capabilities 委托后的 G 段回归；全量回归 **37 脚本 987 项 0 失败**。

### 3.24 v4.15.2（2026-09-07，tag `v4.15.2`）

**小修复：框架目录清单校正 + Statistics 模板翻译补全**。

- **框架目录清单校正（core/framework_manifest.py）**：`documents/` 仅为开发文档（不在精简运行包内、无运行时代码引用，缺失不影响框架运行）——从 `CORE_DIRS` 移除，不再作为致命核心目录；逐一核查其余声明均正确。
- **Statistics 模板翻译补全（v4.14 遗留）**：`templates/admin/dashboard.html`、`stats.html` 硬编码中文全部包裹 `t()`/`T()`，新增词条补入 en.json（124 + 协议 共 125 词条，en 总量 114→239）。
- **测试**：test_i18n 新增"框架模板 t()/T() 中文 key 全覆盖 en.json"断言（28→29 项）；全量回归 **37 脚本 988 项 0 失败**。

### 3.25 v4.15.3（2026-09-07，tag `v4.15.3`）

**小修复：剩余页面模板硬编码中文翻译补全**。

- **剩余模板翻译补全**：`templates/admin/`（plugins.html 141 处、system.html、logs.html、network.html 补 4 处 JS 残留）+ 公开页（index/login/logout/register/setup/plugin_default）硬编码中文全部包裹 `t()`/`T()`；en.json 补 245 词条（239→484，修正 3 个句号差异 → 485）。
- **测试**：test_i18n 覆盖断言保持 29 项（扫描全部框架模板，确保模板中任一中文 key 必被语言包覆盖）；全量回归 **37 脚本 988 项 0 失败**。

### 3.26 v4.15.4（2026-09-09，tag `v4.15.4`）

**稳定版体验优化批次**——各页面语言切换、翻译工具与语言包贡献者字段、若干健壮性修复。

- **各页面语言切换**：所有页面（首页/后台 navbar/插件默认页/注册页/全部错误页）统一加入语言切换入口——深色导航页 `templates/_lang_switch.html` 下拉片段，浅色页用平铺链接；复用 `/lang/<code>?next=` 切换路由（`next={{ request.path }}` 回跳当前页）。
- **翻译工具 `tools/i18n_status.py`**：以 en.json 为完整基准报告各语言翻译进度与贡献者；`--create <lang> --name` 一键基于 en.json 模板创建新语言包（内置 en/zh-CN 受保护不可创建/修改）；`--json` / `--check` / 指定语言。语言包新增 `__contributors` 元信息字段（固定 `__` 前缀，不参与翻译对照）。
- **健壮性修复**：HTTP 跳转端口容错（苹果设备 https 访问 http 跳转端口报 Bad HTTP/0.9 时返回友好提示不再崩日志）；卸载/启动统计孤儿清理（`purge_plugin_stats` / `purge_frontend_tool_stats` / `purge_orphan_stats`）；桌面 dashboard 残留汉堡按钮隐藏；插件空间饼图 Top7+其它归并、IP 变化显示等。
- **测试**：test_i18n 29 项；全量回归 **37 脚本 988 项 0 失败**。
- runtime 91 文件（sha256 `783f9a86...`）。

### 3.27 v4.16.0（2026-09-10，tag `v4.16.0`）

**事件总线 + 插件真依赖解析**——Community 架构能力演进，纯 stdlib 无新增运行时依赖，让插件间、插件与框架间解耦通信，并让依赖声明真正"可校验"。

- **事件总线 core/events.py（新）**：轻量进程内发布-订阅观察者模式，单例 `from core.events import events`。API `on(event, handler, *, once=False, async_=False, priority=0, owner=None)` / `once` / `off(event, handler=None)` / `emit(event, **data)` / `has` / `clear`。**weakref 防泄漏**：可 weakref 的模块级函数用弱引用、宿主回收订阅自动失效；绑定方法/闭包不可 weakref 用强引用 + `owner` 标记。`async_=True` 走后台线程池（ThreadPoolExecutor max_workers=4）不阻塞 emit。事件名约定：全局点分命名空间（`plugin.loaded`/`user.login`/`request.finished`），插件自定义 `plugin.<插件名>:<事件名>`。内置埋点：`plugin.loaded`/`installed`/`uninstalled`/`enabled`/`disabled`（plugin_loader/plugin_admin）、`user.login`/`logout`（auth）、`request.finished`（interceptor）。
- **插件真依赖解析 core/plugin_deps.py（新）**：`parse_dep_spec` 支持 `name`/`name>=x`/`name<y`/`name==z`/`name>=a,<b` 多约束；`_version_tuple` 纯 stdlib 简化 semver（数字段 + 预发布 a/b/rc 权重，`1.0>1.0rc1>1.0b1>1.0a1`）；`version_satisfies`；`resolve_dependency_order`（Kahn 拓扑排序 + 环分组检测）。
- **加载/安装/卸载接入**：plugin_loader 由 DFS 改为 `resolve_dependency_order`（循环不再中止全局加载，改标记剔除）；`check_dependencies` 支持版本约束；`global_var.plugin_load_issues` 记录 `dependency_missing`/`dependency_version`/`dependency_circular`，经 `/api/admin/plugins` 透出并显示后台『未加载』徽章 + 原因；plugin_admin 卸载前反向依赖检查（被依赖则阻止）、安装后依赖缺失告警（不自动安装）、`_set_enabled` 禁用路径清理事件订阅。
- **BasePlugin 事件集成（plugins/base_plugin.py）**：插件无需直接接触 core.events——`on_event(event, handler, *, once=False, async_=False, priority=0)`（自动 owner=self 并登记 `_event_subs`）、`emit_event(name, **data)`（自动加 `plugin:<插件名>:` 前缀）、`event_name(name)`、`_cleanup_events()`；`on_unload` 默认调用 `_cleanup_events`（插件重载应 `super().on_unload()`）。
- **示例插件升级（均已端到端验证）**：scheduler_demo **1.2.0**（on_load 订阅内置 + 自定义 + 异步事件；定时任务 emit_event 发布 heartbeat/stats；页面事件卡片 + 手动发布 manual_trigger + 清空；事件历史持久化）；dependent_demo **2.0.0**（跨插件事件订阅——松耦合订阅 scheduler_demo 事件 + 全局事件，**未在 dependencies 声明 scheduler_demo** 体现解耦；事件来源归因 `_source_of`『跨插件(<name>)』/『框架全局』+ 页面『跨插件事件接收』卡片）。
- **测试**：新增 tests/test_events.py 11 项、tests/test_dependency.py 11 项、tests/test_plugin_events.py 28 项（BasePlugin 集成 + scheduler_demo 事件演示 + dependent_demo 跨插件事件）；framework_manifest 登记 core/events.py、core/plugin_deps.py；全量回归 **40 脚本 0 失败**。

### 3.28 v4.17.0（2026-09-10，tag `v4.17.0`）

**移动端/桌面端页面分离**——脱离 v4.13『桌面端 + `xxx_mobile.css`/`mobile.js` 样式补充』模式，改为同 URL + 服务端 UA 检测分发独立模板。纯 stdlib 无新增运行时依赖。

- **设备检测 core/device.py（新）**：`detect_device(user_agent)`（复用 `core/stats.classify_device`，bot 视为 desktop）返回 `mobile`/`tablet`/`desktop`；`get_device()`（读当前请求 UA）；`is_mobile()`（仅手机端为 True，tablet 走桌面端响应式避免退化）；`mobile_enabled()`；`resolve_template(name)`（手机端且存在 `templates/mobile/<name>` 则用移动端模板，否则安全回退桌面端）；`render(template, **ctx)` 统一渲染入口。配置 `MOBILE_ENABLED`/`FORCE_MOBILE`；app.py `inject_device` context_processor 注入 `is_mobile`/`device`。
- **框架公开页移动端模板**：新增 `templates/mobile/login.html`、`templates/mobile/index.html` + `static/css/mobile-app.css` 精简移动端布局层；`routes/public.py` 登录页/首页改用 `device.render` 分发；错误页沿用响应式 base 降低风险。
- **后台分发挂点**：`routes/admin.py` `_admin_page` 改用 `device.render`，开放 `mobile/admin/<template>` 独立能力；后台沿用响应式 base 保底。
- **BasePlugin 移动端能力（plugins/base_plugin.py）**：`_resolve_template(template, mobile=False)`（mobile=True 优先查找 `plugins/<name>/mobile/<template>`）；`is_mobile_context()`/`mobile_template()`；`render()`/`render_plugin_page()` 移动端自动分发；`routes/plugin.py` 子页面分发接入。插件接入移动端独立渲染只需放 `templates/plugins/<name>/mobile/` 同名模板。
- **示例插件 corp_tools 升级 1.1.0**：新增 `templates/plugins/corp_tools/mobile/` 下 4 个同名移动端独立模板（主入口 + health/links/notices），精简 DOM、触屏友好、复用 mobile-app.css，脱离 corp_mobile.css 样式补充；require_framework_version 4.17.0；真实移动/桌面 UA 端到端验证通过。
- **测试**：新增 tests/test_device.py 20 项（UA 分类 / 配置开关 / resolve_template 分发 / 公开页移动端模板 / BasePlugin 移动端命名空间，用 DictLoader 注入避免写工作区）；framework_manifest 登记 core/device.py；ci.yml 加 test_device；开发规范/README/examples 同步。

### 3.29 v4.17.1（2026-09-11，tag `v4.17.1`）

**签名功能验证 + 自更新/插件更新源验签 bug 修复**——补全"密钥存在时"签名特性测试，暴露并修复 `_verify_feed_signature` 构造验签 manifest 漏传 signature 字段的缺陷。

- **修复（2 处）**：`core/update_checker.py`、`core/plugin_updates.py` 的 `_verify_feed_signature` 构造验签 manifest 时只取 SIGNED_FIELDS 字段、漏传 `signature`，导致 `verify_signature` 永远返回『未签名』拒绝——配置 `UPDATE_PUBLIC_KEY_PEM` 后自更新/插件更新源签名实际永远无法通过验证。修复：两处各补 `manifest['signature'] = d.get('signature')`。
- **新增签名专项测试（2 个脚本）**：tests/test_plugin_updates.py（8 项，插件更新源签名：未配公钥放行 / 有效签名通过 / 篡改·无签名·错误公钥·公钥文件不存在拒绝 / 未声明更新源）；tests/test_release_sign.py（5 项，发布签名联动：release write_changelog --sign 产出含 signature / 配公钥验证通过 / 篡改拒绝 / 签名失败不写缓存 / 错误公钥拒绝）。
- **扩展签名测试**：test_package_sign.py 22→25 项（路由端到端：配公钥后签名包 200 / 签名被篡改 400 / 未签名包 200）；test_update_checker.py 43→50 项（自更新签名验签 7 场景）。
- **工具链实操**：tools/package.py genkey→pack --sign→verify 全流程验证（正确公钥通过 / 错误公钥拒绝 / 加料篡改拒绝）。
- **全量回归 43 脚本 1143 项 0 失败**。

### 3.30 v4.17.2（2026-09-11，tag `v4.17.2`）

**AirDrop 框架协调清单 A+C 组**——插件包/工具包开发体验与健壮性收口（不含 B 组新功能 save_uploads，缓置 v4.18）。

- **6.3 描述一致性冲突报错附两处值**（`core/plugin_pack.py`）：冲突拒绝时逐字段附 `plugin.json值 vs 类属性值`（list/dict 用 JSON 序列化，如 `dependencies`/`pip_dependencies`），替代原先仅列字段名、需手工 diff 定位；test_pack_meta.py 22→23 项（新增断言验证两处值都出现）。
- **6.4 描述文件失效打标 + 后台标注**（`core/plugin_cache.py` / `core/plugin_loader.py` / `templates/admin/plugins.html` / `locales/en.json`）：插件描述 json 非法时告警由 warning 升级为 error 并给 `info` 打标 `meta_invalid`，经 plugin_loader 透传进插件目录与 `/api/admin/plugins`；后台插件列表新增红色『描述文件失效』徽章 + tooltip（说明 capabilities 等声明被忽略）；test_meta_e2e.py 10→11 项。
- **6.5 源码→分发包自动映射**（`tools/package.py` / Dev-Guide 5.6.9）：pack 新增 `--src-layout`（backend）把源码布局（`<name>.json + <name>.py + frontend/`）自动映射为分发布局（`plugin.json + 主.py + templates/static`），自动排除 `configs/`/`__pycache__` 等；新增 tests/test_src_layout.py 16 项（映射规则 + cmd_pack 产物 + parse 可解析）。
- **6.6 CRLF 规范提示**（Dev-Guide 5.6.9）：插件文本文件统一 LF 的规范说明 + `.gitattributes` 示例，规避 Windows 下 CRLF/`\r\r\n` 污染。
- **CI 与文档同步**：CI 测试数组补入 test_src_layout；Dev-Guide 第 12/14 章测试表、工具表、运行命令同步；README 双版测试数 43→44 脚本 / 1143→1161 断言。
- **全量回归 44 脚本 1161 项 0 失败**。

### 3.31 v4.18.0（2026-09-11，tag `v4.18.0`）

**AirDrop 框架协调清单 B 组——同步持久化上传助手（§6.1/§6.2）**，补齐 `save_uploaded_file` 仅覆盖"异步-临时目录"场景、缺"同步直接落盘"上传助手的空缺，把各插件手写的净化 + 去重 + 双预检 + 落盘收敛为框架一次调用。

- **BasePlugin 新增 3 项**（`plugins/base_plugin.py`）：`upload_dir` 属性（持久化上传目录，相对 BASE_DIR 优先）、`sanitize_filename(filename)` 静态方法（路径穿越安全统一策略，比 core.utils.secure_filename_cn 更严：删危险字符 / 移除 `..` 与前导点 / 空名兜底）、`save_uploads(file_key='files', dest_dir=None, *, dedup=True, sanitize=True, max_upload_mb=None)`（单/多文件 getlist、净化、重名加序号、单文件大小与存储配额双预检、直接落盘，返回每文件独立结果列表，部分成功语义；dest_dir 与 upload_dir 皆空抛 ValueError）。
- **测试**：新增 tests/test_plugin_uploads.py 21 项（T1 单文件 / T2 多文件 / T3 大小超限 / T4a 配额超限 / T4b 未配配额放行 / T5a-c 净化 / T6a-c 去重与覆盖 / T7 类型拒绝 / T8a-c 缺失·空·跳过 / T9 部分成功 / T10a-b 目录创建与缺省 / T11 enforce 交叉校验未声明目录）。
- **AirDrop 迁移**：`get_safe_filename`→`self.sanitize_filename`（6 处调用 + 删除手写方法），`upload_files`→`save_uploads`（`dest_dir=self.upload_folder`，保持前端返回格式 200/400/413 等价）；删除多余 import re。
- **文档**：Dev-Guide 5.4.2 新增 `save_uploads`/`sanitize_filename`/`upload_dir` 表项与同步落盘说明 + enforce 一致性；README 双版"统一文件传输"能力补充同步上传助手；CI 补 test_plugin_uploads。
- **全量回归 45 脚本 1182 项 0 失败**。

### 3.32 v4.19.0（2026-09-11，tag `v4.19.0`）

**全量界面深色模式 + setup.html 双语并显**，主题能力收敛到 core/theme.py，前端经 `data-theme` + 语义 CSS 变量实现深浅切换，无独立主题文件、可向多主题扩展。

- **后端主题能力**（`core/theme.py` 新增）：`available_themes()` 返回 auto/light/dark 注册表；`resolve_theme(candidate)` 白名单校验防注入、非法回退 auto；`get_theme()` 优先级 Cookie `theme` > 用户配置 `THEME` > auto。`global_var.py` CONFIG_ITEMS 新增 `THEME`（default auto）；`routes/public.py` 新增 `GET /theme/<code>` 路由（白名单 + next 开放重定向防护）；`app.py` inject_i18n 注入 `theme`/`available_themes`。
- **前端**（`static/js/theme.js` 新增）：设置 `<html data-theme>`（dark/light）；auto 用 `matchMedia('(prefers-color-scheme: dark)')` 解析并监听变化；暴露 `window.Theme`（apply/switch/declared/current）；从 `<html data-theme-init>` 读初始主题。`templates/_theme_switch.html` 导航栏主题下拉组件（auto/light/dark 三链接）。
- **CSS 深色**：main.css 补充 `:root` 语义变量（--input-bg/--muted/--chip-bg/--panel-tint/--req-*/--th-bg/--code-*）+ `:root[data-theme="dark"]` 覆盖集；error.css 自包含变量 + dark 覆盖；admin/base.html 插入 `--adm-*` 变量 + dark 覆盖（6 子页正文色变量化）；mobile.css 追加 plugin_default 移动端适配。
- **模板接入**：16 个模板加 data-theme-init + theme.js；三导航栏页/login/register/setup/mobile 加入主题入口。
- **setup.html 双语并显**：routes/public.py 注入 zh_t/en_t/primary_lang/secondary_lang/available_langs；模板每处文本 `.bi-zh`/`.bi-en` 双份渲染 + `<body data-lang-active>` + CSS 主次控制，内联 JS 切换主次语言与 `<html lang>`（迎合国际化）。
- **语言包**：en.json 新增 6 主题词条（跟随系统/浅色/深色/主题/切换主题/自动）。
- **测试**：新增 tests/test_theme.py 10 项（A 白名单解析 / B Cookie 与用户配置优先级 / C auto 深浅解析与模板注入）；扩展 test_setup（双语断言 + 隔离目录复制语言包）；test_i18n 29 / test_setup 19 / test_page_router 21 / test_error_pages 12 / test_admin_api 69 / test_permission 20 全绿；浏览器端到端（setup/首页/登录/注册/登出/404/plugin_default）深色全部生效；plugin_default 截图确认。
- **发布清单**：framework_manifest.py CORE_FILES 登记 core/theme.py；CI 补 test_theme。
- **全量回归 46 脚本 1194 项 0 失败**。

### 3.33 v4.19.1（2026-09-11，插件主题接入便利化）

**插件主题便利化**（响应 AirDrop 主题协调清单 6.7）：此前插件页面默认不含主题接入、CSS 语义变量集内联在 main.css、BasePlugin 无主题辅助、主题切换组件仅框架页面 include。本次以"上下文 + 后端解析 API + 独立 theme.css"最小侵入方案补齐，示例插件展示多页面深色接入。

- **后端解析 API**（`core/theme.py` 新增 `resolve_effective_theme(candidate=None)`）：`light`→light、`dark`→dark、`auto`/非法→`auto`（实际深浅交前端 `theme.js` 解析）；省略入参取 `get_theme()`（Cookie > 用户配置 > auto）。`auto` 语义诚实——后端无法读浏览器 `prefers-color-scheme`，只返回 `'auto'`。`app.py` inject_i18n 注入 `theme_effective` 到所有模板（含插件页面），插件模板可直接 `data-theme-init="{{ theme_effective }}"`。
- **独立 theme.css**（`static/css/theme.css` 新增）：`:root` 浅色语义变量集 + `:root[data-theme="dark"]` 深色覆盖集；main.css 顶部改 `@import "theme.css";`（删除内联变量定义）。框架页面与插件共享同一套语义变量，深色覆盖单点维护。
- **插件接入样板**（`examples/plugins/multitool_demo` 升 1.1.0，require 4.19.0）：4 个模板加主题三件套——`<html data-theme-init="{{ theme_effective }}">` + `<link /static/css/theme.css>` + `<script /static/js/theme.js>`；demo.css 末尾补 `:root[data-theme="dark"]` 覆盖映射到 theme.css 变量。manifest.json / examples/README.md 补深色接入说明。
- **框架防御修复**（`core/frontend_tools.py` migrate_legacy_config）：旧版路径 `BASE_DIR/frontend_tools.json` 与新版 `FRONTEND_CONFIG_FILE` 解析到同一路径时（如隔离测试将 FRONTEND_CONFIG_FILE mock 到 BASE_DIR 根，或人为配置重合），不再把唯一一份有效配置当“冗余旧版”误删——新增同路径 normpath 判断直接跳过。修复前 test_frontend_permission 在隔离目录下 15 项工具 404（配置被 migrate 误删），修复后 25/25 全过。
- **测试**：test_theme 扩展 A4（`resolve_effective_theme`：light/dark 实际值、auto/非法交前端），删冗余 C4/C5，11/11；主题相关回归子集全绿（theme 11 / i18n 29 / setup 19 / page_router 21 / error_pages 12 / admin_api 69）；示例插件打包验证（zip 内 version 1.1.0 与 require 4.19.0 一致）+ 模板 Jinja 可编译 + 端到端渲染验证 17/17（隔离目录加载 multitool_demo，主入口/子页默认 `data-theme-init="auto"`、Cookie dark 时 `="dark"`、theme.css/theme.js 注入、`/static/css/theme.css` 可访问、main.css 含 `@import`）。全量回归 46 脚本 1195 项 0 失败。

### 3.34 v4.19.2（2026-09-12，可扩展主题：themes/ 目录扫描）

实现 AirDrop 交接方案的 themes/ 目录扫描（可扩展主题），在 v4.19.1 语义变量体系之上，让用户通过 `themes/<name>/{theme.json,theme.css}` 自定义主题，本地目录发现（Community 边界内）。

- **后端扫描**（`core/theme.py`）：新增 `THEMES_DIR`（global_var 可配置，默认 `BASE_DIR/themes`）+ 主题名白名单正则 `^[a-zA-Z0-9_-]+$`；`available_themes()` 内建 auto/light/dark + 扫描 themes/ 子目录（读 theme.json，name 须与目录名一致），带 mtime 缓存，**运行期增删主题/改 theme.json 即失效**；新增 `get_theme_css(name)` 读自定义主题 CSS（白名单 + 非内建 + 存在才返回）。
- **前端**（`static/js/theme.js`）：`KNOWN` 从 `<html data-themes>`（available_themes 的 tojson）动态读取；自定义主题直接设 `data-theme=<name>` 并动态挂载 `/theme-static/<name>/theme.css`，CSS 加载失败（404，主题被删）回退 `auto` 作视觉兜底。
- **路由与注入**：新增 `/theme-static/<name>/theme.css`（白名单 + 只读，不存在 404）；框架 16 模板 + multitool_demo 4 模板统一追加 `data-themes`；切换器 `_theme_switch.html` 改为从 available_themes 动态渲染下拉（内建保留翻译/图标，自定义显示 title）。
- **兜底（自定义主题运行期被删）**：后端 `get_theme`/`resolve_theme`/`resolve_effective_theme` 经 `_is_valid_theme`（动态 available_themes）自动回退 `auto`，且**不清 Cookie**（偏好保留，重放回目录自动恢复）；前端 CSS 404 回退 `auto`。
- **示例主题**：框架自带 `themes/sepia/`（完整语义变量覆盖集）。
- **测试**：test_theme 扩展可扩展主题场景（扫描发现/非法名忽略/运行期新增生效/get_theme_css/动态白名单解析/被删兜底/theme-static 白名单/data-themes 注入），11→25 项；前端 jsdom 验证（KNOWN 动态/切换自定义/CSS 挂载/404 回退）11 项；multitool_demo + sepia 端到端集成 21 项。全量回归见发布记录。

### 3.35 v4.20.0（2026-09-12，用户中心）

**用户中心（审核符合 Community 原则）**：登录用户可自助修改自己的昵称与密码，用户名（登录名）不可改；仅本人自助，管理员管理他人账号仍走内置 user_manage（不新增角色层级，避免触碰 RBAC 细化，归 Enterprise）。

- **后端自助改昵称**（`plugins/auth.py`）：新增 `update_nickname(user_id, nickname)`（非空、≤20、去空白）+ `update_nickname_api()`（POST `/api/auth/user/update-nickname`，需登录，仅本人，同步 `request.user.nickname`）。
- **页面**：新增 `GET /user-center`（`routes/public.py`），经 interceptor `LOGIN_GUARD_PREFIXES` 守卫（未登录 302 `/login`）；前端 `templates/user_center.html` + `static/js/user_center.js`（主题三件套，改昵称 + 改密码聚合）。
- **入口**：后台导航栏 + 公开页导航（`index.js` 登录态）加"用户中心"链接；v4.10 强制改密弹窗保留并提示可前往用户中心完整修改。
- **测试**：新增 test_user_center（改昵称仅本人/空/超长/成功/去空白 + 用户名不可改 + /user-center 未登录 302/登录 200 渲染，13 项）+ jsdom 前端（改昵称/改密校验与请求体，12 项）；test_setup 强制改密 19 项不回归。全量回归见发布记录。

### 3.36 v4.20.1（2026-09-12，update_checker 重启后未重新获取修复）

**修复**：`core/update_checker.py` `background_check()` 改为 `check_for_update(force=True)`——此前启动后台线程调 `check_for_update()`（无 force）会命中缓存 TTL（`UPDATE_CHECK_INTERVAL` 默认 24h），导致"有缓存时重启框架后未重新远程获取更新版本"。启动是低频事件，每次重启强制拉取最新版本并写缓存；TTL 缓存仍用于抑制运行中手动非强制检查（后台不带 force 的刷新）。

**测试**：`test_update_checker` 新增 5b 段（写入未过期旧缓存 1.0.0 → 设 `UPDATE_FEED_URL` 为新版本源 8.8.8 → 调 `background_check()` → 断言缓存更新为新版本），50→52 项；`test_release_sign` 5、`test_plugin_updates` 8 不回归。全量回归 47 脚本 1224 项。

## 4. 发布实践沉淀

- **changelog.json 是发布强制同步点**：`tools/release.py build` 会重写（latest_version/sha256/download_url/changes），须随 Release 一起 commit + push（v4.9.0/v4.9.1 曾漏同步，v4.9.2 补齐并固化）。
- **四端点同步**：`global_var.FRAMEWORK_VERSION` + `tests/test_admin_api.py` 断言 + README 双版徽章 + `SYSTEM_VERSION_LABEL`（release.py bump 自动同步三处 + 徽章）。
- **Release 完整流程**：release.py build（拿 sha256 + 写 changelog）→ git commit（README/changelog）→ git tag + push → gh release create 上传 zip + Release notes → 端到端验证（raw changelog.json 200 + zip 下载 sha256 比对）。
- **覆盖发布**：同版本号重新发布时，用 `gh release upload <tag> <zip> --clobber` 覆盖资产；Release 描述与 changelog sha256 必须同步更新，避免更新校验链断裂。
- **README 故事段维护**：保持精简（主题里程碑聚合），细节指向开发规范与本演进记录，避免随版本膨胀。
- **release.py bump 锚点必须是"当前版本"**：版本替换锚点曾误用"新版本号"（v4.8.0 引入，首次使用即暴露）——替换锚点应从 `global_var.FRAMEWORK_VERSION` 读取当前值，而不是目标新值；发布工具链改动必须经真实 bump 演练（v4.10 M7 修复）。
- **runtime 精简包内容随版本核对**：新增面向使用者的工具（如 v4.10 的 scaffold/install_plugin）必须补进 `RUNTIME_TOP`，否则离线包缺文件（v4.10 曾漏 tools/）。
- **回归数字统一口径**：README / 开发规范 / SECURITY.md / 演进记录统一使用本地全量实测口径（35 脚本 914 项，2026-09-07 v4.15 复核；此前 807/779 系版本记录估算值），CI 含 AirDrop 子项目测试口径另计，避免文档间数字漂移。
