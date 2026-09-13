## v4.20.0 — 用户中心（改昵称 + 改密码）

审核符合 Community 原则：登录用户可自助修改自己昵称与密码，**用户名不可改**，仅本人自助。

### 新增
- **后端自助改昵称**：`plugins/auth.py` 新增 `update_nickname()` + `update_nickname_api()`（`POST /api/auth/user/update-nickname`，body `{nickname}`，非空/≤20 字符/去空白，成功同步 `request.user.nickname`，`/api/auth/user/info` 立即返回新值）。
- **独立页面 `/user-center`**：经 `routes/interceptor.py` `LOGIN_GUARD_PREFIXES` 守卫（未登录自动 302 到 `/login`）；前端 `templates/user_center.html` + `static/js/user_center.js`（主题三件套，改昵称 + 改密码聚合表单）。
- **导航入口**：后台导航栏 + 公开页导航（`index.js` 登录态）加"用户中心"链接；v4.10 强制改密弹窗保留为提醒，并提示可前往用户中心完整修改。
- 复用既有改密能力：`POST /api/auth/change-password`（校验旧密码、≥6 位、踢除其他会话）。

### 边界
- 用户名（登录名）创建后不可改；仅本人自助；管理员管理他人账号仍走内置 `user_manage`（不新增角色层级，避免触碰 RBAC 细化，归 Enterprise）。

### 验证
- 新增 `test_user_center`（改昵称仅本人/空/超长/成功/去空白 + 用户名不可改 + `/user-center` 未登录 302/登录 200 渲染，13 项）+ jsdom 前端（改昵称/改密校验与请求体，12 项）；`test_setup` 强制改密 19 项不回归；`en.json` 补 14 个新 key 翻译。
- 全量回归 **47 脚本 1222 项 0 失败**。
- runtime 包 sha256：`07656b1dd8f33986f50d03a85002e50f3ecef6bb073c0420f601b300e3bce043`
