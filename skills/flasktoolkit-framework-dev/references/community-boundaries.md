# Community 边界与范围判定

本页是 FlaskToolkit 开发**任何改动前**的第一道检查。在开始写代码、改配置、加依赖前，先用本文判定本次改动是否落在 Community 定位内。

权威来源：`{FRAMEWORK_ROOT}/documents/Enterprise-Edition-Handover-Roadmap.md`（交接文档，最新修订以仓库为准）。

## Community 与 Enterprise 分界

| 维度 | Community Edition（v4.x，当前） | Enterprise Edition（v5.x，规划） |
|------|--------------------------------|--------------------------------|
| 定位 | 小型局域网/个人用户 | 企业级远期计划 |
| 功能状态 | **非功能冻结**：架构规模有意识控制，持续迭代；新功能贴合个人/局域网则评估实现，企业级引导 Enterprise | 由接手方团队主导 |
| 范围判定 | 贴合个人/局域网/插件开发则实现；企业级归 Enterprise | 承接 Community 已实现的『企业向能力』作为起点 |

**核心口径**：Community 是**立场**——专注小型局域网/个人场景，功能与维护持续迭代，但不为满足企业级诉求而无限做深。

## 三类越界能力（Community 上不深化，仅必要 bug 修复）

以下能力已在 v4.x 落地，因偏企业/生态，**归入 Enterprise 交接资产**，Community 不再加深：

1. **深层安全体系**（v4.3~4.9）：静态扫描、运行时审计钩子、capabilities 白名单、完整性签名。Community 信任模型本为「插件可信直接执行」。
2. **平台/生态能力**（v4.15 Root 域）：framework 能力域三档（read/manage/core）、程序化插件管理服务层、插件级更新源 + RSA 验签——为第三方插件市场铺路。
3. **企业部署复杂度**（v4.12 Secure）：反向代理支持（TRUST_PROXY_HEADERS/EXTERNAL_SCHEME）、自签名 HTTPS 多阶段评估。

> 对这些能力：Community 上只做**必要的 bug 修复**，不新增深化特性。若要深化，引导 Enterprise 讨论。

## Community 范围判定清单（提出新功能时先行对照）

**贴合 Community → 评估实现**：
- 局域网可达（地址/mDNS/IP 变化/桌面启动器）
- 移动端/桌面端适配、响应式
- 统计洞察、i18n 语言切换
- 个人装机体验（首次向导/强制改密/邀请码注册）
- 插件开发友好（脚手架/离线安装/依赖解析/事件总线）
- 稳定维护（回归+CI+文档）

**企业级越界 → 引导 Enterprise 讨论，Community 不实现**：
- 深层安全：进程级沙箱 / RBAC 权限细化 / CSP 严格化 / 集中签名中心
- 平台生态：第三方插件市场 / 程序化插件管理服务层 / 插件级签名更新源
- 企业部署：LDAP/OAuth2/SSO、Docker/systemd 服务化、多租户与水平扩展、配置加密/密钥管理

## 产品名称合规（BSD-3 许可约束）

- 品牌名只能用 **FlaskToolkit**；界面/文档/词条/链接文本中**不得**把 "Flask" 单独用作自家产品品牌。
- Flask 是 Pallets 的 BSD-3 项目，协议第 3 条禁止未经许可背书/推广衍生品。
- 技术性引用（如「基于 Flask」）、文件名路径标识、Changelog 历史旧名**可保留**。
