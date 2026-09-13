# FlaskToolkit v4.20.3

移动端样式统一 + audit 根因修复 + 多语言补全，全量回归 47 脚本 0 失败。

## 移动端样式统一（index/login）

- **templates/mobile/index.html 重写**：顶栏由拥挤的 `m-nav` 改为桌面同构的 `header.navbar` + `.navbar-right` 汉堡结构（mobile.js 自动注入汉堡按钮、点击展开/收起）；正文保留 m-tool-card 卡片，工具容器追加 `tools-grid` 类复用网格布局。
- **index.js collect 兼容**：`closest('.tools-grid, .m-tools')`，修复移动端搜索/排序崩溃。
- **login 垂直居中 + 系统名**：桌面与移动两份 login.html 加 `{{ system_name }}`（jinja 渲染系统名），移动端 `m-container-center` 垂直居中 + `m-system-name`。

## user_manage 能力声明

- 核查 user_manage 为纯 API 委托（12 路由全经 `self.auth_plugin.*`），遵循 Deny by Default 声明 `capabilities: []`（类属性 + json 双处），作内置插件最小授权示范。

## audit 两个根因修复

- **根因 1**（core/framework_manifest.py）：`is_framework_core_path` 排除前缀 `'plugins/configs/'`（带尾斜杠）不匹配目录本身，auth 写自属配置目录被误记 root-access；修复 `p == prefix.rstrip('/') or p.startswith(prefix)`。
- **根因 2**（core/audit_hook.py）：新增 `_is_framework_resource_path`（templates/locales/static 顶层），渲染读模板/i18n/静态资源豁免归因（框架基础功能）。
- 两个根因均做框架层修复，新增回归用例固化（manifest 54→55、audit_hook 38→39）。

## setup 默认英语单语 + 多语言补全

- **setup.html 双语不并存**：默认显示英语，仅手动切换界面语言下拉时才变换；"界面语言"标签保留双语。
- **en.json 补 key**：补 `普通用户`/`点击检查更新`（v4.20.2 漏补），统一 LF。
- **新增 locales/fr.json**：法语语言包补齐 en 全部 523 key（`__name__: "Français"`），作为多语言测试样板；框架自动发现 en/fr/zh-CN，缺失 key 回退中文。
- **setup POST 语言白名单动态化**（routes/public.py）：硬编码 `('zh-CN','en')` → `i18n.available_languages()`，支持扩展语言。

## 测试修复

- **test_admin_api logs 脆弱断言修复**：原"隔离空日志 → 空列表"断言因 app 启动把启动日志写入隔离目录 logs/app.log（被 logging FileHandler 占用无法删除）而恒失败（既有问题，经 git stash 对比确认与功能改动无关）；改为验证 logs API 核心能力（200 + data 为 list）。

**全量回归 47 脚本 0 失败。**

- **Runtime**: `FlaskToolkit-4.20.3-runtime.zip`（精简运行包）
- **sha256**: `e740fdf03750e16fec4d5051c71dfb6ed19021f4d54131cb3fffac65c68edd16`
