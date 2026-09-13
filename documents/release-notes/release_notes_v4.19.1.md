## v4.19.1 — 插件主题接入便利化 + 前端工具配置防误删

响应 AirDrop 主题协调清单 6.7，为插件接入深色模式提供最小侵入路径（上下文 + 后端解析 API + 独立 theme.css）。

### 新增
- **后端解析 API**：`core/theme.py` 新增 `resolve_effective_theme(candidate=None)` —— `light/dark` 返回实际值，`auto`/非法交前端 `theme.js` 解析；省略入参取 `get_theme()`（Cookie > 用户配置 > auto）。
- **上下文注入**：`app.py` inject_i18n 注入 `theme_effective` 到**所有模板（含插件页面）**，插件模板可直接 `data-theme-init="{{ theme_effective }}"`。
- **独立 theme.css**：`static/css/theme.css`（`:root` 语义变量 + `:root[data-theme="dark"]` 覆盖集），框架 `main.css` 改 `@import` 共享，深色覆盖单点维护。
- **示例插件**：`multitool_demo` 升 **1.1.0**（require 4.19.0），4 模板加主题三件套，demo.css 补 dark 覆盖映射；Dev-Guide 5.11 新增插件接入主题文档。

### 修复
- **框架防御**：`migrate_legacy_config` 旧版路径与 `FRONTEND_CONFIG_FILE` 解析到同一路径时不再把唯一一份有效配置当"冗余旧版"误删（修复隔离环境 test_frontend_permission 15 项工具 404，现 25/25 全过）。

### 验证
- `test_theme` 扩展 A4（resolve_effective_theme），11/11；示例插件打包验证 + 端到端渲染 17/17。
- 全量回归 **46 脚本 1195 项 0 失败**。
- runtime 包 sha256：`9c133b7d860c332c647405b32f03952994963022e8b4845db220502d598638c3`
