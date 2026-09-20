# FlaskToolkit v4.23.0

pip 依赖安装拦截 + 统计实时刷新 + 打包工具增强 + 跨平台目录打开，全量回归 49 脚本 0 失败。

## 插件安装拦截缺 pip 依赖

- **core/plugin_deps.py**：新增 `check_pip_dependencies(pip_dependencies)`，复用 `parse_dep_spec` / `version_satisfies`，返回 `[(spec, '未安装'/'版本不满足')]`。
- **core/plugin_admin.py**：`install_from_package` / `update_from_package` 在解包前硬拦截——plugin.json 声明的 pip 依赖缺失/版本不满足时拒绝安装，彻底消除"装成功却被跳过加载"的困惑。
- **routes/admin.py**：`preview` 返回 `pip_missing`；前端 plugins.html 对缺失依赖渲染红色警示。

## 前端统计实时刷新

- plugins.html 四张统计卡片 `stat-value` 加 id（`stat-total-plugins` 等），新增 `refreshStats()` 拉 `/api/admin/stats` 更新，在 `loadPlugins()` 内调用——安装/卸载插件后免刷新页面即可看到数量变化。

## 打包工具 package.py 增强

- 新增 `--exclude` 参数，可在打包时排除指定文件/目录。
- `-o` 输出已存在时提示覆写/重命名（`_resolve_output`），`-y` 自动接受覆写。

## 修复与体验

- **修复 Windows 下静态 `.js` 被误判 `text/plain` 拒执行**（theme.js / login.js 等）：app.py 初始化时 `mimetypes.init()` + `add_type('application/javascript','.js')`，一处全局注册覆盖主 static / plugin_static / theme-static / frontend_static 所有 .js。
- **修复 plugins.html Jinja 注释误写**：注释内 `{{ stats.* }}` 改为 `stats.*`，消除模板语法错误。
- **管理后台打开项目目录**：dashboard.html / system.html 点击项目目录行，经后端 `POST /api/admin/open-dir`（`admin_api` 保护）调用系统文件管理器打开文件夹——Windows `os.startfile` / macOS `open` / Linux `xdg-open`；realpath 前缀校验限定 `BASE_DIR` 内，空路径/项目外/非目录/失败均静默返回 False（前后端不提示）。

## 测试与文档

- test_dependency.py 新增 `test_check_pip_dependencies`（12 项），dev guide 十二章与 README 双版脚本/断言数同步为 49 scripts / 1324 assertions。

**全量回归 49 脚本 0 失败。**

- **Runtime**: `FlaskToolkit-4.23.0-runtime.zip`（精简运行包）
- **sha256**: `d6e3637021c9ec3ce5579fa57d5ff6b1df9e0bf0bb1d39e4460622a8364d6ce6`
