# FlaskToolkit v4.15.4（稳定版体验优化批次）

稳定版维护期体验优化与健壮性修复。所有页面统一加入语言切换，新增翻译工具与语言包贡献者元信息字段。

## 更新内容

- **各页面语言切换**：首页 / 后台 / 插件默认页 / 注册页 / 全部 7 个错误页统一加入语言切换入口（深色导航页下拉片段、浅色页平铺链接），切换后回跳当前页。
- **翻译工具 `tools/i18n_status.py`**：以 en.json 为完整基准报告各语言翻译进度与贡献者；`--create` 一键创建新语言包（内置 en/zh-CN 受保护）；`--json` / `--check` 供 CI 使用。
- **语言包 `__contributors` 元信息字段**：固定 `__` 前缀（与 `__name__` 一致），记录翻译贡献者，鼓励 GitHub 翻译贡献。
- **健壮性修复**：
  - HTTP 跳转端口容错——修复苹果设备用 `https://` 访问 http 跳转端口报 `Bad HTTP/0.9 request type`；
  - 卸载与启动时清理统计孤儿数据（`call_stats` / `daily_stats` / `frontend_access_stats`，覆盖后台卸载、CLI 离线卸载）；
  - 桌面端 dashboard 残留汉堡按钮隐藏；
  - 插件空间饼图 Top7 + 其它插件归并、dashboard IP 变化显示修复、network 提示顺序修复、插件拖拽上传 / 配置按钮按 has_config 显隐 / 移除恢复出厂、首页空状态修复等。

## 测试

全量回归 **37 脚本 / 988 项 0 失败**；GitHub Actions 在 Python 3.10 / 3.11 / 3.12 自动执行。

## 下载

- runtime 包：`FlaskToolkit-4.15.4-runtime.zip`（sha256 `783f9a86f0824727f9cc50088075a53162d652df396f1ed88a8316674aeb1cb6`）
