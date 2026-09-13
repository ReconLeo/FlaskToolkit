## v4.20.2 稳定性测试累积 bug 修复

稳定性测试（Pydroid, Python 3.13.2）新发现并修复的一批框架 bug，全量回归 47 脚本 0 失败。

### 后端
- P0 日志初始化清理（`core/logging_setup.py`）：移除 `handlers.clear()` 与 `propagate=False`，避免重复初始化清掉 handler / 日志不向父级传播。
- 并发 `load_plugins` 竞态（`core/plugin_loader.py`）：watcher 线程 × API 线程同时重导入导致 `_load_unlocked` KeyError，加全局互斥锁串行化。
- audit 钩子 int fd 误判（`core/audit_hook.py`）：`open(fd)` 的 int 描述符被误当路径，生成伪能力 `filesystem:read:10/` 等，现已跳过。
- quota 未声明插件默认配额（`core/quota.py`）：`all_plugins_quota` 遍历全局插件注册表，未建 data 目录的插件（如 AirDrop/user_manage）按默认配额列出。
- /api/admin/quota total（`routes/admin.py`）：总用量从插件级 usage 汇总，修复 total 显示 0.00MB。
- 昵称修改同步会话（`plugins/auth.py`）：改昵称同步活跃会话 nickname 快照；会话临时文件加唯一后缀防并发覆盖。
- IP 检测保存即时生效（`core/ip_watcher.py` + `routes/admin.py`）：`get_status` 从 config 权威读取，保存 `IP_WATCH_INTERVAL` 即时重启检测线程。
- host 字段同源（`routes/admin.py`）：`/api/admin/system/info` host 改用 `network.get_binding_host()`，与 network 接口一致。
- **release 打包缺陷**（`tools/release.py`）：runtime 精简包整体排除 `templates/plugins/`，内置插件 `user_manage` 模板缺失致页面 500；改为保留内置 `user_manage` 的模板与静态资源。

### 前端（备忘 9-29）
- 登录移动端崩溃、上传预览态复原、用户中心改 button、toolSort 深色、plugins 页去系统管理按钮。
- 后台汉堡抽屉 + userBox/userInfo 悬浮卡片 + theme/lang 收纳 + 深色 badge/notice-warn、network 深色、system 版本手动/自动检查、plugin_default 窄屏。
- 移动端导航平滑展开/收起、theme/lang 点击 toggle、admin-indicator 位于 user-text 右侧。

> 运行包 sha256：`7b2a77ceb1325c881da424b4315d8b8eb32cc20791e54e2f932058d8459daf00`
