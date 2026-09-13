## v4.15.3 — 剩余页面模板硬编码中文翻译补全

### 新增 / 修复
- 剩余模板硬编码中文翻译补全：`templates/admin/`（plugins 141 处 / system / logs / network 补 4 处 JS）+ 公开页（index / login / logout / register / setup / plugin_default）硬编码中文全部包裹为 `{{ t('...') }}`（服务端）/ `window.T('...')`（客户端）
- admin base 模板内联 JS 用 `window.T`，公开页（不继承 base、无 window.T）内联 JS 用服务端 `{{ t('...') }}` 渲染；含内嵌引号的示例 placeholder 拆为无引号 key，避免 i18n 正则截断
- `locales/en.json` 补 245 词条（239 → 485），并统一 LF 行尾

### 测试
- `test_i18n` 覆盖断言保持 29 项（扫描全部框架模板，确保模板中任一中文 key 必被语言包覆盖）
- 全量回归 **37 脚本 988 项 0 失败**

### 文档
- README 双版补 v4.15.2/4.15.3 i18n 全面补全特性（en 词条 485）
- 开发规范 v4.15.3 段 + 版本表
