# FlaskToolkit 插件框架 Roadmap

| 版本 | v4.1（稳定版前） | 更新日期 | 2026年08月23日 |
|------|----------------|---------|---------------|

> 本文档梳理框架在 **v4 系列转入稳定版前** 的提升方向，按优先级（P0 安全/数据完整性 → P1 测试/工程化 → P2 体验/可维护性）分级，并标注每项的落地状态。具体开发规范见《Flask插件框架开发规范-v4.0.md》。

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
| v4.2.0（当前） | 框架版本升级 4.1.0→4.2.0；大插件多模板页面路由（page=True + 模板命名空间 + render 助手）；示例 multitool_demo；回归测试 16 脚本 306 项（CI 已接入） |
| v4.1.0（已完成） | P0/P1/P2 全落地；回归测试入项目 tests/（222 项）；配置 CLI（tools/config.py）；tools/backup.py + reset.py 备份/深度重置；启动完整性自检；CI 接入 |
| v4.1.0（规划） | CI 接入；P2 项按需选取 |
