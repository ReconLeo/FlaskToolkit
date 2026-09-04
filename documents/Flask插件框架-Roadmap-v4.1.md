# FlaskToolkit 插件框架 Roadmap

| 版本 | v4.3（安全大更新） | 更新日期 | 2026年09月03日 |
|------|-------------------|---------|---------------|

> 本文档梳理框架的提升方向：v4.1 稳定版前（P0 安全/数据完整性 → P1 测试/工程化 → P2 体验/可维护性）与 **v4.3 安全大更新**（见第六章）。每项标注落地状态，具体开发规范见《Flask插件框架开发规范-v4.0.md》。

---

## 一、现状基线（v4.1 已具备能力）

- 插件化全栈工具集：后端 Python 插件（插件包 .zip）+ 前端 HTML 工具混合展示，统一入口/统一管理。
- 权限体系：游客 / 登录 / 管理员三层，由插件装饰器声明；auth 为可选插件（内置）。
- 安全能力：前后端插件包 zip slip 双防线（专项测试）、上传大小限制（413）、CSRF 双提交、HttpOnly Cookie 鉴权、日志轮转（RotatingFileHandler 10MB×5）。
- 管理后台：dashboard / plugins / logs / stats / system 五页面 + Factory Reset（部分/全部）+ 统一错误码页面（400/401/403/404/405/500）。
- 工程化：热加载（watchdog）、模板自动重载、插件配置 UI、回归测试套件（12 个脚本，238+ 项）。

---

## 二、P0 — 安全与数据完整性（稳定版发布前应完成）

| # | 提升项 | 状态 | 说明 |
|---|-------|------|------|
| P0-1 | **上传大小限制落地** | ✅ 已完成（v4.1） | 管理后台上传的插件包/前端工具包统一受 `PACKAGE_MAX_UPLOAD_SIZE`（10MB）限制，超限返回 413。已由 `test_admin_api.py`（插件包）与 `test_frontend_chain.py`（工具包）覆盖。 |
| P0-2 | **插件信任模型文档化** | ✅ 已完成（v4.1） | 开发规范新增「插件信任模型与安全」章节：明确插件即代码、无沙箱隔离、安装即信任作者。沙箱/签名等运行时隔离暂不落地。 |
| P0-3 | **Factory Reset 自动备份** | ⏸ 搁置（决策） | Factory Reset 设计意图即恢复初始状态，此操作导致的数据丢失由用户自行承担，**不实现自动备份**。已改为在管理后台重置弹窗中强化风险提示（不可撤销、务必先手动备份 plugins/configs、data、frontend_tools.json 等）。 |

---

## 三、P1 — 测试与工程化（稳定版质量保障）

| # | 提升项 | 状态 | 说明 |
|---|-------|------|------|
| P1-1 | **requirements 版本锁定** | ✅ 已完成（v4.1） | `requirements.txt` 固化已验证版本（Flask==3.1.3、Flask-Cors==6.0.5、APScheduler==3.11.3、watchdog==6.0.0）；新增 `requirements-dev.txt` 说明测试依赖与运行命令。 |
| P1-2 | **测试套件补全** | ✅ 已完成（v4.1） | 新增 4 个测试（均为隔离目录模式，不污染真实项目）：`test_frontend_chain.py`（前端工具链路 23 项）、`test_admin_api.py`（管理 API 21 项）、`test_factory_reset.py`（重置范围 37 项）、`test_error_pages.py`（错误码页面 12 项）。全套回归 12 脚本 238+ 项。 |
| P1-3 | **CI 接入** | 📋 计划 | `.github/` 缺失，当前回归靠手动运行。建议接入 GitHub Actions：push/PR 时跑全量回归（12 脚本）+ 自动清理 auth.json/temp 污染。 |

---

## 四、P2 — 体验与可维护性（稳定版后可迭代）

| # | 提升项 | 状态 | 说明 |
|---|-------|------|------|
| P2-1 | 上传体验增强 | ✅ 已完成（v4.1） | 管理后台上传/更新表单：文件选择后显示大小；>10MB 前置校验并拒绝提交；XHR 上传进度条（plugin_common 自动注入 CSRF）。 |
| P2-2 | 审计日志 | ✅ 已完成（v4.1） | 新增 `core/audit.py`（JSONL 落盘 data/audit.log）+ `/api/admin/audit` 接口；挂点：后端插件安装/更新/卸载/启用/禁用、前端工具安装/更新/卸载/启用/禁用、Factory Reset；系统管理页新增「最近操作」区块。Factory Reset 各 scope 不清除审计日志。 |
| P2-3 | 插件溯源 | ✅ 已完成（v4.1） | 后端插件 status.json 扩展（source/install_time/version/history），前端工具 frontend_tools.json 条目扩展；插件列表合并溯源字段，卡片展示安装时间/来源/版本历史。 |
| P2-4 | 插件包签名校验（信任模型增强） | ✅ 已完成（v4.1） | 方案C：包内 `manifest.json` 记录全部成员 sha256，安装时完整性校验（防篡改/损坏/zip slip 错位/加料）；可选 RSA-SHA256 签名（`PLUGIN_PUBLIC_KEY_PEM` 配置公钥后强制验签）；`PACKAGE_INTEGRITY_MODE` strict/warn/off 三档。独立命令行工具 `tools/package.py`（genkey/pack/verify/show，支持 --sign 签名）。专项测试 test_package_sign.py 22 项。 |

---

## 五、版本状态对照

| 版本 | 状态 |
|------|------|
| v4.7.0（当前） | 装饰性更新 F2/F3：项目宣传（启动横幅/后台页眉 GitHub 链接/系统管理页关于卡片/system/info 项目字段）+ 系统名个性化（SYSTEM_NAME/SYSTEM_VERSION_LABEL 配置项 + Jinja 全局注入 + 登录页/首页/后台/错误页硬编码系统名变量化，仅装饰不影响内部逻辑）；回归 22 脚本 500 项 |
| v4.6.0（已完成） | 审计钩子归因修复：enforce 下插件加载链路（框架加载器帧）与辅助模块（非 BasePlugin 类）归因两缺陷修复；test_audit_hook 新增 B4/B5；回归 22 脚本 499 项；严格模式预设（strict）D1-D8 系统验证通过 |
| v4.5.1（已完成） | 登录锁定手动解封：auth 新增 unlock_user/is_user_locked；user_manage 新增 POST /api/user_manage/unlock + 用户列表 locked 状态 + 前端解封按钮；回归 22 脚本 497 项 |
| v4.5.0（已完成） | 收尾：可选 HTTPS（SSL_CERT_FILE/SSL_KEY_FILE + tools/gen_cert.py 自签名证书）；frontend_tools.json 默认路径迁移 data/（旧文件自动迁移）；auth 会话迁移插件自属目录；审计钩子框架路径过滤；selfcheck CORE_FILES 补全；回归 22 脚本 482 项 |
| v4.4.0（已完成） | 运行时审计钩子（P1 阶段三）：sys.addaudithook 事件监听 + 栈归因 + AUDIT_HOOK_MODE 三档（off/observe/enforce）+ 网络白名单阻断 + 未授权行为按插件聚合展示（前端合计）+ suggest_for_action 建议声明复用；回归 22 脚本 482 项 |
| v4.3.2（已完成） | 插件 capabilities 声明模型（P1 阶段二）：8 域能力白名单 + 安装交叉校验 + 建议声明生成 + 自属路径隐式豁免 + base_plugin data_dir API + 运行时授权基准；回归 21 脚本 447 项 |
| v4.3.1（已完成） | 插件静态扫描 + 配置预设（P1 阶段一）：AST 扫描器、PLUGIN_SCAN_MODE 门禁、tools/scan.py、config profile 三预设；回归 20 脚本 396 项 |
| v4.3.0（已完成） | 系统安全强化（P0）：安全响应头/Cookie 加固/空闲超时/登录锁定；回归 19 脚本 361 项 |
| v4.2.2（已完成） | 文件传输强化：全局上传上限/route 级覆盖/中文名下载/Range；on_ready 钩子 |
| v4.2.1（已完成） | public_page 豁免 + CSRF 单值注入修复 |
| v4.2.0（已完成） | 框架版本升级 4.1.0→4.2.0；大插件多模板页面路由（page=True + 模板命名空间 + render 助手）；示例 multitool_demo；回归测试 16 脚本 306 项（CI 已接入） |
| v4.1.0（已完成） | P0/P1/P2 全落地；回归测试入项目 tests/（222 项）；配置 CLI（tools/config.py）；tools/backup.py + reset.py 备份/深度重置；启动完整性自检；CI 接入 |
| v4.1.0（规划） | CI 接入；P2 项按需选取 |


---

## 六、v4.3 安全大更新（Security Hardening，2026-09 起）

> 背景：框架已在可信局域网自托管场景稳定运行，启动针对**外部（局域网环境暴露面）**与**内部（插件恶意代码）**的双重安全加固。整体分三阶段渐进合入，每阶段独立成版本、独立回归。审计建议整合：①分散的"严格模式"开关收拢为配置预设；②插件读写范围显式声明；③联网声明细化为网络白名单（类防火墙）。

| 阶段 | 版本 | 状态 | 内容 |
|------|------|------|------|
| P0 系统安全强化 | **v4.3.0** | ✅ 已完成（`f71b000`） | 统一安全响应头（CSP/X-Frame-Options/nosniff/no-referrer/Permissions-Policy + 移除指纹头）；会话 Cookie 加固（HttpOnly+SameSite+可选 Secure）；会话空闲超时（30 分钟）；登录失败锁定三档（ip_username/username/off，阈值可配置，锁定期间通用 429）。全部配置项经 config CLI 调整。 |
| P1-阶段一 静态扫描 | **v4.3.1** | ✅ 已完成（`20763b4`） | `core/plugin_scanner.py` AST 级扫描器（危险导入/调用、动态执行、混淆检测、socket 服务端、实例别名归因、范围提取 paths_read/paths_written/network_endpoints）+ 前端 HTML 正则扫描；安装链路门禁 `PLUGIN_SCAN_MODE`（off/report/enforce）四端点接入；`tools/scan.py` 分发前自检 CLI；`tools/config.py profile` 三套配置预设（daily/strict/lan-open）。回归 20 脚本 396 项。 |
| P1-阶段二 capabilities 声明模型 | **v4.3.2** | ✅ 已完成 | 插件能力白名单声明（Deny by Default）：plugin.json 可选 `capabilities` 字段，8 大域能力目录（filesystem/network/webhook/process/scheduler/database/device/env），安装时与静态扫描范围**交叉校验**产生 mismatch 清单；**自属路径隐式豁免**（plugins/configs/<name>.json、plugins/data/<name>/**、plugins/temp/<name>/**，base_plugin 框架化 data_dir API）；建议声明自动生成（suggested_capabilities）；声明结果落盘成为阶段三运行时授权基准。 |
| P1-阶段三 运行时审计钩子 | **v4.4.0** | ✅ 已完成 | `sys.addaudithook` 监听 open/os.remove/subprocess.Popen/socket.connect/socket.bind；调用栈 plugins/ 来源判定插件归属；`AUDIT_HOOK_MODE` 三档（off/observe 默认记录未授权访问/enforce 按 capabilities + 网络白名单阻断——"防火墙"落地）；与 core/audit.py JSONL 审计日志整合。 |
| 远期规划 | — | 📋 暂不实施 | 权限模型细化（超级管理员/普通管理员仅管理特定功能）；进程级沙箱（内存/CPU 配额）；CSP 收紧为严格策略。 |

**阶段依赖链**：静态扫描（范围输出=事实基准）→ capabilities 声明（授权声明）→ 运行时审计钩子（以声明为授权依据的运行时防线）。三阶段构成"安装时静态审查 → 安装时授权比对 → 运行时兜底"的纵深防御。**P1 安全强化已全部完成。**
