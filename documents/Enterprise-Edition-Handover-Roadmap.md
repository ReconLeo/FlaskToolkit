# FlaskToolkit Enterprise Edition — 交接与路线（v5.x）

> 状态：**公开招募接手者**（2026-09-05，最新修订 2026-09-09）
> 本文件是 Enterprise Edition 的交接声明与未来路线说明。Community Edition **非功能冻结，而是架构规模有意识控制**（专注小型局域网/个人用户场景），功能与维护持续迭代（截至最新 v4.15.4）；Enterprise Edition 的远期计划（含权限模型细化等）因超出当前小团队的承担能力，公开寻求接手。

---

## 一、Community 与 Enterprise 的分界

| 维度 | Community Edition（v4.x，当前） | Enterprise Edition（v5.x，规划） |
|------|-------------------------------|----------------------------------|
| 定位 | 插件化全栈工具集，可信局域网/内网自托管，**架构规模有意识控制**（专注小型局域网/个人用户） | 企业级权限与治理能力，面向更严格的合规与多角色协作 |
| 功能状态 | **非功能冻结**：架构规模有意识控制，持续迭代（v4.8.0 起分割 Release，最新 v4.15.4）；新功能贴合小型局域网/个人场景则评估实现，企业级需求引导至 Enterprise 讨论 | 在 5.x 正式推出远期计划能力（见第二章），设计由接手方主导 |
| 维护承诺 | 回归保障持续有效（37 脚本 988 项 + GitHub Actions CI），维护者可继续修复与合入 | 无固定承诺，由接手方团队接管后自行规划 |
| 范围判定 | 见本章『Community 范围判定』：贴合个人/局域网/插件开发则实现；深层安全、平台生态、企业部署能力归 Enterprise | 承接 Community 已实现的『企业向能力』作为起点（见第二章末） |
| 仓库 | 当前公开仓库 `ReconLeo/FlaskToolkit`（main 分支）持续维护 | 可 fork 演进，或经 issue / 邮件联系原作者协商交接方式 |

**Community 维护与范围边界（承诺）**：
- **新功能范围判定**：贴合小型局域网 / 个人用户 / 插件开发友好 → 评估实现；企业级（深层安全 / 平台生态 / 企业部署）→ 引导至 Enterprise 讨论，Community 不实现。详见下节『Community 范围判定』。
- 照常接受：bug 修复、安全必需补丁、文档修正、示例维护、依赖升级、发布流程优化。
- 每次变更继续走版本收尾 checklist（版本号同步 / 配置核对 / 回归 988 项 / 文档双同步 / 提交推送）。
- 接收 Enterprise 路线的**讨论与设计建议**，但不承诺实现时间。

**Community 范围判定**（提出新功能时先行对照）：
- 贴合 Community → 实现：局域网可达（地址/mDNS/IP 变化/桌面启动器）、移动端适配、统计洞察、i18n 语言切换、个人装机体验（首次向导/强制改密/邀请码注册）、插件开发友好（脚手架/离线安装/依赖解析/事件总线）。
- 企业级越界 → 引导 Enterprise 讨论：深层安全（进程级沙箱/RBAC 权限细化/CSP 严格化/集中签名中心）、平台生态（第三方插件市场/程序化插件管理服务层/插件级签名更新源）、企业部署（LDAP/OAuth2/SSO、Docker/systemd 服务化、多租户与水平扩展、配置加密/密钥管理）。

---

## 二、Enterprise Edition 远期路线（5.x）

以下能力自 v4.x 起即列为远期规划，**作为 Enterprise Edition 的功能候选清单**，接手方可在此基础上调整优先级与范围：

### 2.1 权限模型细化（首要候选）
- **现状**：三层权限（public / user / admin）+ auth 可选插件 + 插件级 `@permission` 装饰器 + 前端工具三层访问控制。
- **规划方向**：
  - 超级管理员 / 普通管理员分级（普通管理员仅可管理特定插件或功能域）；
  - 基于角色的访问控制（RBAC）：角色 → 权限集合 → 用户/组绑定；
  - 插件 API 级细粒度授权（可按端点/方法/数据范围授权）；
  - 审计报表增强（按角色/用户/插件聚合的合规报表）。

### 2.2 进程级沙箱（长期候选）
- **现状**：插件在进程内运行，静态扫描 / capabilities 声明 / 运行时审计钩子为**风险缓解**而非绝对隔离（见开发规范 10.1 信任模型）。
- **规划方向**：内存 / CPU 配额（`resource` 或容器化）、插件独立进程或子解释器、文件系统与网络面的强隔离。

### 2.3 CSP 收紧为严格策略
- **现状**：CSP 为"宽"策略（允许 inline script/style 兼容存量插件）。
- **规划方向**：配合插件静态扫描与前端工具规范，收紧为严格 nonce / hash 策略。

### 2.3b Community 已实现的『企业向能力』（接手起点）

Community 在推进中已将若干偏企业/生态的能力落地，可直接作为 Enterprise 的演进基础（继续深化或将硬编码参数企业化）：
- **Root 权限域**（v4.15.0）：framework 能力域三档 read/manage/core（core≈Linux root），程序化插件管理服务层 `core/plugin_admin.py`。
- **插件级签名更新源**（v4.15.0）：`core/plugin_updates.py`（repo/update_feed + RSA 验签 + 更新徽章）——集中签名中心的基础。
- **深层安全体系**（4.3~4.9，延续至 v4.15）：静态扫描 `core/plugin_scanner.py`、capabilities 能力声明、运行时审计钩子 `core/audit_hook.py`（off/observe/enforce）、完整性签名 `core/package_sign.py`、数据配额 `core/quota.py`（存储域声明 + 全局总量）——`进程级沙箱`与`CSP 严格化`的缓解层已就绪。
- **反代与 HTTPS 部署**（v4.12）：自签名证书 `tools/gen_cert.py`、HTTP→HTTPS 308 自动跳转、`SESSION_COOKIE_SECURE` 自动配置、反代支持（TRUST_PROXY_HEADERS/EXTERNAL_SCHEME/HOST/PORT）——`Docker/systemd 服务化`的基础。
- **i18n 框架**（v4.9.0）：`core/i18n.py` 轻量语言框架（locales/<lang>.json + 插件语言包合并查找链 + t() 模板/后端/前端）——`国际化完善`已具雏形。

> 说明：这些能力在 Community 仅按个人/局域网规模实现，接手方可在 Enterprise 上按更大规模与企业化参数深化（见 2.1~2.4 规划方向）。

### 2.4 可扩展方向（供接手方评估）
- 插件市场 / 集中签名中心（插件分发与更新签名托管）；
- 企业身份对接：LDAP / OAuth2 / SSO 登录源；
- 多租户与水平扩展（多实例部署、会话与统计数据外部化）；
- 部署形态：Docker / systemd 服务化、配置加密（密钥管理）、备份自动化；
- 国际化完善（前端文案 / 文档英文化）。

---

## 三、架构地图（接手必读）

> 详细规格以 `documents/Flask-Plugin-Framework-Dev-Guide-v4.md` 为唯一权威出处（目录树、API、插件格式），本节为模块职责速览。

### 3.1 顶层结构与启动链路

```
app.py          纯入口（初始化 Flask/CORS/scheduler、register_routes(app)、关闭钩子、main）
global_var.py   纯路径常量 + 共享状态 + CONFIG_ITEMS 配置注册（无第三方 import）
core/           服务层（不依赖 app 实例）
routes/         路由层（register(app) 注入）
plugins/        插件目录（base_plugin 基类 + auth/user_manage 内置插件 + 用户插件）
templates/      页面模板（admin/ 管理后台 + plugins/ 插件页面 + 错误页）
static/         js/css（plugin_common.js 统一鉴权前端）
tools/          运维/发布 CLI
tests/          回归测试（37 脚本 988 项，隔离目录模式）
documents/      权威文档（开发规范 / Roadmap / 版本收尾 checklist / 本交接文档）
```

### 3.2 模块职责明细

| 模块 | 职责 |
|------|------|
| `core/permission.py` | 权限体系：`@permission("public"/"user"/"admin")` 装饰器、CSRF 校验、三层判定 |
| `core/plugin_loader.py` | 插件加载/卸载、拓扑排序、依赖检查（on_ready 就绪钩子） |
| `core/plugin_cache.py` | 插件指纹缓存（磁盘扫描结果缓存） |
| `core/watcher.py` | watchdog 热重载 |
| `core/plugin_status.py` | 插件状态与调用统计 |
| `core/frontend_tools.py` | 前端工具包注册/分发/静态资源（permission 三层） |
| `core/stats.py` | 统计聚合（API 热度、访问统计） |
| `core/logging_setup.py` | 日志（RotatingFileHandler 10MB×5） |
| `core/audit.py` | 审计日志 JSONL 落盘 + current_actor |
| `core/package_sign.py` | 插件包完整性校验与签名（方案C：sha256 + 可选签名） |
| `core/plugin_scanner.py` | 静态扫描（AST 后端 + 正则前端，范围提取） |
| `core/capabilities.py` | 能力声明模型（8 大域，隐式豁免，交叉校验） |
| `core/audit_hook.py` | 运行时审计钩子（sys.addaudithook，observe/enforce） |
| `core/selfcheck.py` | 启动完整性自检（CORE_FILES 致命清单） |
| `core/update_checker.py` | 版本检查（changelog.json 数据源 + 签名校验 + TTL 缓存） |
| `core/network.py` | 地址中心（局域网 IP/绑定/端口三级优先/访问地址组合，纯标准库） |
| `core/mdns.py` | mDNS 广播（可选 zeroconf，flasktoolkit.local） |
| `core/ip_watcher.py` | IP 变化检测（启动横幅播报） |
| `core/quota.py` | 数据配额（存储域声明 + check_upload 上传预检 + 全局总量） |
| `core/i18n.py` | 轻量语言框架（locales/<lang>.json + 插件语言包合并查找链 + t()） |
| `core/framework_manifest.py` | 框架目录清单统一（驱动自检/升级/备份/重置/Root 判定） |
| `core/plugin_admin.py` | 程序化插件管理服务层 |
| `core/plugin_updates.py` | 插件级更新源（repo/update_feed + RSA 验签） |
| `routes/interceptor.py` | 全局鉴权拦截（/plugin/ 守卫、public_page 豁免） |
| `routes/public.py` | 公共页面（首页/登录/登出/裸插件调试）与错误处理 |
| `routes/plugin.py` | 插件分发（/api/<plugin>/<path> 通配路由） |
| `routes/frontend.py` | 前端工具分发（/frontend/<name> + /frontend-static/） |
| `routes/admin.py` | 管理端 API（@admin_api 保护，系统/插件/统计/日志/更新检查） |
| `routes/security.py` | 统一安全响应头（SECURITY_HEADERS） |
| `plugins/base_plugin.py` | 插件基类：生命周期钩子、@permission、data_dir/get_data_path、静态路由、send_file_response |
| `plugins/auth.py` | 可选鉴权插件：PBKDF2 / HttpOnly Cookie+CSRF / 登录锁定 / 空闲超时 / 手动解封 |
| `tools/config.py` | 配置 CLI（show/set/unset/profile 三套预设） |
| `tools/package.py` | 打包/签名/校验 CLI（--type backend/frontend） |
| `tools/backup.py` / `tools/reset.py` | 备份恢复 / 深度重置 |
| `tools/scan.py` | 分发前静态扫描 CLI |
| `tools/gen_cert.py` | HTTPS 自签名证书生成 |
| `tools/desktop_launcher.py` | 桌面启动器（tkinter GUI，subprocess 解耦） |
| `tools/i18n_status.py` | 翻译进度/贡献者工具（--create 建语言包） |
| `tools/update.py` | 双后端更新（git / archive，USER_DATA_PATHS 用户数据保留） |
| `tools/release.py` | 发布工具链（bump 版本 / 精简·全量·定制包 / changelog 签名） |

### 3.3 关键设计约束（改动前必读）

1. **auth 是可选插件**：不安装 auth 时全员放行；安装后启用鉴权。
2. **API 三层权限由插件自声明**：插件 routes 用装饰器声明，非全局硬编码路径前缀。
3. **插件包机制**：.zip（plugin.json + 主 .py + 可选 templates/static），installed_files 卸载清单，require_framework_version 门槛。
4. **纵深防御三阶段**：静态扫描（安装时事实）→ capabilities 声明（安装时授权比对）→ 运行时审计钩子（运行时兜底），`PLUGIN_SCAN_MODE` / `AUDIT_HOOK_MODE` / `PACKAGE_INTEGRITY_MODE` 三档联动。
5. **用户数据与代码分离**：`data/`、`plugins/data/`、`plugins/configs/`、`logs/` 等为运行时数据（gitignore + USER_DATA_PATHS 清单），更新/备份/重置不得破坏。
6. **配置优先级**：环境变量（仅 HOST/PORT/DEBUG）> 用户配置（data/user_config.json）> 默认值。

---

## 四、工程流程指引（接手后日常操作）

### 4.1 环境与测试

```bash
git clone https://github.com/ReconLeo/FlaskToolkit.git
cd FlaskToolkit
pip install -r requirements.txt -r requirements-dev.txt
python app.py                    # 启动（默认 127.0.0.1，FLASKTOOLKIT_HOST/PORT/DEBUG 可调）
# 回归：37 脚本 988 项（隔离目录模式，不污染项目文件）
for t in tests/test_*.py; do python "$t"; done
```

### 4.2 发布流程（版本收尾）

1. 功能/修复合入 → 全量回归 988 项；
2. 按 `documents/Release-Wrapup-Checklist.md` 逐项核对（版本号三处同步 / 配置核对 / 数据路径迁移 / 检修一致性 / 示例同步 / 行尾 / 回归 / **文档双同步** / 提交推送 / 记忆沉淀）；
3. 发布包：`python tools/release.py --bump-version X.Y.Z` → `--build`（精简包）或 `--build-full`（全量包）/ `--include src:dest`（定制包）→ 上传 GitHub Release → `write_changelog --sign` 重新生成 changelog.json；
4. 企业内网升级：`python tools/update.py check/backup/apply/rollback`（archive 后端自动跳过 USER_DATA_PATHS）。

### 4.3 贡献规范

- 遵循 `CONTRIBUTING.md`；允许使用 AI 辅助工具，但提交者对正确性/安全/合规负责，AI 生成代码须过回归与审查。
- 文档边界：README=门面（英文主版 + 中文版同步），开发规范=权威规格，Roadmap=路线，本文件=交接与分界。

---

## 五、接手指引

**如果你是潜在接手者（个人或团队）**：

1. 先通读：README（门面）→ 本文件（交接/路线/架构）→ 开发规范（规格）→ Roadmap（历史路线）；
2. 运行测试与启动服务，动手尝试插件开发（参考 `examples/` 官方示例与 `documents/archive/Plugin-Design-corp_tools.md`）；
3. 对 Enterprise 路线（第二章）中感兴趣的能力，通过 GitHub Issue 发起讨论或直接提交设计提案；
4. 若希望 fork 独立演进：请保留 Community 分支的维护通道（建议上游 Community 继续回 PR），并保持 LICENSE 兼容（MIT 允许商业使用，保留署名）。

**交接边界**：
- 原团队不承担 Enterprise 的 SLA 承诺；可协商：架构咨询、设计评审、代码 review 支持；
- 原团队保留对 Community 仓库的日常维护权与发布权；
- 交接后 Enterprise 分支/仓库的命名与品牌由接手方决定（建议保留 FlaskToolkit 名称的派生声明）。

---

## 六、变更记录

| 日期 | 变更 |
|------|------|
| 2026-09-05 | 初版：Community/Enterprise 分界 + 远期路线 + 架构地图 + 接手指引（Community 收尾文档整理） |
| 2026-09-09 | 对齐最新定位：Community 改为『非功能冻结、架构规模有意识控制、持续迭代（最新 v4.15.4）』；新增『Community 范围判定』（贴合个人/局域网则实现，企业级越界归 Enterprise）；新增 2.3b 『Community 已实现的企业向能力』作为接手起点；回归数字 540→988；架构地图补 v4.11~v4.15 新增模块 |
