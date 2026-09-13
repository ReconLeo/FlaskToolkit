## v4.19.2 — 可扩展主题（themes/ 目录扫描）

实现 AirDrop 交接方案，让主题可扩展：放入 `themes/<name>/` 目录即被发现并生效，无需改代码（Community 边界内）。

### 新增
- **后端扫描**：`core/theme.py` 的 `available_themes()` 内建 auto/light/dark + 扫描 `THEMES_DIR`（默认 `BASE_DIR/themes`）子目录（读 theme.json），带 mtime 缓存、**运行期增删主题/改 theme.json 即生效**；主题名白名单正则 `^[a-zA-Z0-9_-]+$` 防注入；新增 `get_theme_css()`。
- **主题 CSS 服务**：`GET /theme-static/<name>/theme.css`（白名单 + 只读，不存在 404）。
- **前端**：`theme.js` 的 `KNOWN` 从 `<html data-themes>` 动态读取；自定义主题直接设 `data-theme=<name>` 并动态挂载 `/theme-static/<name>/theme.css`。
- **切换器**：`_theme_switch.html` 从 `available_themes` 动态渲染下拉（内建 auto/light/dark 保留翻译与图标，自定义显示 title）。
- **示例主题**：自带 `themes/sepia/`（完整语义变量覆盖集，可作模板）。

### 兜底（自定义主题运行期被删）
- 后端 `get_theme` / `resolve_theme` / `resolve_effective_theme` 自动回退 `auto`，且**不清 Cookie**（偏好保留，重放回目录自动恢复）。
- 前端自定义主题 CSS 加载失败（404）回退 `auto` 作视觉兜底。

### 验证
- `test_theme` 11→25（扫描发现/非法名忽略/运行期生效/get_theme_css/动态白名单/被删兜底/theme-static 白名单/data-themes 注入）+ 前端 jsdom 11 项 + multitool+sepia 端到端集成 21 项。
- 全量回归 **46 脚本 1209 项 0 失败**。
- runtime 包 sha256：`9e1d07f5c7e91a4cd511b4d1ab7cc1fb02ae3cdde9a9bb8054e3d53c8726d16b`
