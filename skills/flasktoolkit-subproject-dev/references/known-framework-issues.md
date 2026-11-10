# 框架已知缺陷避坑清单（子插件开发）

来源：记忆 `wiki/lessons` 系列复盘，均为真实复现。**子插件开发时对照本表，识别"是插件问题还是框架问题"**；框架侧未修复项既是插件内 workaround 的依据，也是应写入协调清单的发现。

每条列出：现象 / 何时触发 / 现状（已修复=插件侧无需规避；未修复=插件内 workaround + 上报协调清单）。

## A. 会影响插件功能的缺陷（多为已修复，识别以免误判）

### A1. 配置 BOM 静默失效（FTK-001，已修复 v4.23.1）
- 现象：`user_config.json` 带 BOM 时配置静默失效，安全开关 `enforce` 静默回落 `observe` 无告警；`cmd_set`/`cmd_unset` 读失败后空 dict 覆盖写回丢配置。
- 触发：Windows 记事本 / PowerShell 5.1 `Set-Content -Encoding UTF8` 默认写 BOM。
- 现状：框架 `USER_CONFIG_FILE` 读取点已统一 `utf-8-sig`；写回类命令解析失败中止而非空 dict 覆盖。
- 插件侧：自读自写配置统一 `utf-8-sig`；**安全相关配置解析失败必须 `logging.warning` 留痕，绝不静默**。

### A2. 点分模块导入漏报（FTK-002，已修复 v4.23.1）
- 现象：`import urllib.request` 记首段 `urllib` 配不上 `MEDIUM_IMPORTS` 的 `'urllib.request'`；动态 URL 场景审查 scope 为空。
- 现状：导入检查同时比完整名与首段；`MEDIUM_CALLS` 补齐 `urllib.request` 系列。
- 插件侧：用点分模块（`urllib.request` 等）时，确认审查报告能呈现真实外发能力，别因 scope 为空误以为"扫描没拦截"。

### A3. 卸载残留 `__pycache__`（FTK-003，已修复 v4.23.1）
- 现象：离线卸载后 `plugins/<name>/__pycache__/*.pyc` 残留空壳目录。
- 现状：卸载按清单删 + 显式清理 `plugins/<name>/__pycache__` + 剪枝空目录，范围限定插件自有编译产物。
- 插件侧：打包前清 pycache；不要把运行时编译产物当数据。

### A4. audit_hook 插件归因两缺陷（已修复 v4.6.0）
- 现象：①enforce 下任何插件无法安装/加载（加载器帧误归因为插件）；②插件包辅助模块被归因为独立插件名 → 主插件自属路径隐式豁免失效、异步落盘静默失败。
- 现状：框架优先归因"定义了 BasePlugin 子类"的最近帧，辅助模块帧跳过。
- 插件侧：辅助模块（非 BasePlugin 子类）落盘到 `plugins/data/<name>/` 隐式豁免按**主插件名**判定，注意命名一致；异步落盘别吞异常（静默失败难查）。

### A5. 插件语言包安装缺失（已修复 v4.21）
- 现象：`extract_plugin_pack` 忽略 `locales/`，带语言包插件安装后 `self.t()` 回退中文。
- 现状：`locales/` 分支已加，解压到 `plugins/<name>/locales/*.json` 并计入 installed_files。
- 插件侧：新增 `{{ t('...') }}` 词条须同步进自带 `locales/en.json`；测试 i18n 用 `c.set_cookie('lang','en')`（cookie jar），**不能**用 `headers={'Cookie': ...}`（test_client 不解析进 request.cookies）。

### A6. `/plugin/<name>` 页面 500（route 缺 name，已修复 v4.8.0）
- 现象：纯 API 路由插件（routes 无 `name` 键）且无主模板、无 `page()` 时，登录后访问 `/plugin/<name>` 走默认调试页 → `KeyError: 'name'` → 500。
- 现状：`render_plugin_page` 已 `route.get('name', path)` 容错。
- 插件侧：给 routes 加 `name` 字段更稳（同 user_manage 风格），并尽量提供主模板或 `page()`。

### A7. `save_uploaded_file` 落盘项目根（已修复 v4.23.x）
- 现象：未走 loader 直接实例化 BasePlugin 子类（测试/独立使用）调 `save_uploaded_file`，占位符被当相对路径写到项目根 `__NEW_PLUGIN_DEFAULT__/` 并累积。
- 现状：入口对默认占位符兜底，重定向到 `plugins/temp/<name>`。
- 插件侧：直接实例化测试上传时确认走了插件专属临时目录；**`plugins/temp/` 仍无自动清理**，如需可插件内定时清。

### A8. 插件静态资源 404（sys.argv[0] 推导，已修复 v4.10）
- 现象：`register_static_routes` 用 `sys.argv[0]` 推导静态根，从非项目根启动时 `/plugin-static/<name>/...` 404。
- 现状：改用 `global_var.BASE_DIR`。
- 插件侧：从工作区/任意非项目根 cwd 启动做隔离验证时，确认静态资源 200。

### A9. `/plugin/` 页面登录守卫无法按插件豁免（已修复 v4.11）
- 现象：装了 auth 插件后，所有 `/plugin/<name>` 页面被全局守卫强制登录，即使 API 全 public。
- 现状：interceptor 增加插件级豁免，插件声明 `public_page=True` 时页面免登录。
- 插件侧：公开型插件（免登录工具/落地页）须设 `self.public_page = not self.auth_required` 之类并联动；默认 False 不影响他人。

### A10. `# scan:ignore` 对 `import` 永久失效 → subprocess 插件在 enforce 下装不上（FTK-XI-01，已修复 v4.23.5）
- 现象：`PLUGIN_SCAN_MODE=enforce` 时任何 `import subprocess` 的插件都被拒；在 import 行与调用行都写 `# scan:ignore` 也只有调用行生效（`import` 那条 `ignored` 恒为 false）；声明 `capabilities: ["process:exec:ffmpeg"]` 也救不回来。作者只剩 `--no-scan`（整体跳过扫描）或把模式降级到 report。
- 根因：import 类 finding 行号被写死为 `0`，而 `# scan:ignore` 是按行号匹配的 → 永不命中；安装期 capabilities 只判"有没有 process 域"，与真实可执行名无关（运行期 audit_hook 才按 basename 比对）。
- 现状（v4.23.5）：import finding 记真实行号；子进程按可执行名归因，**必须声明匹配的 `process:exec:<bin>`** 才放行；动态构造命令拒绝；拒绝原因逐条可操作。
- 插件侧：按 [plugin-authoring.md](plugin-authoring.md) §7.1 的"三件事"写（import 行 ignore + 调用行 ignore + 精确 `process:exec:<bin>` 声明 + 命令写成字面量）。

### A11. `install_plugin.py --base` 不切换扫描模式（FTK-XI-03，已修复 v4.23.5）
- 现象：把隔离运行时的 `PLUGIN_SCAN_MODE` 改成 `enforce` 后安装高风险插件仍 `[OK]`；只有改**工具所属框架**的配置才生效。隔离测试里据此得出"门禁形同虚设"的结论是错的。
- 根因：CLI 通过 `sys.path` 引入**自身框架**的 `global_var`，`resolve_base()` 只 patch 路径常量，不读 `--base` 的配置。
- 现状（v4.23.5）：新增 `--scan-mode off|report|enforce` 显式覆盖，并**始终打印「生效模式 + 来源」**；`--base` 语义保持"只切路径不切配置"。
- 插件侧：隔离测试要验 enforce 就显式传 `--scan-mode enforce`，并看一眼首行打印的模式来源。

### A12. `package.py pack` 不创建输出目录（FTK-XI-02，已修复 v4.23.5）
- 现象：`pack src -o dist/x.zip` 在 `dist/` 不存在时抛 `FileNotFoundError` traceback（首次打包必踩）。
- 现状（v4.23.5）：自动创建父目录（含交互重命名的分支）。
- 插件侧：无需规避；老版本脚本里多余的 `mkdir -p dist` 可以留着。

## B. 未修复的框架缺陷（插件内 workaround + 上报协调清单）

### B1. 插件安装不检查 pip 依赖（**已修复**：v4.23.0 Web 硬拦截 / v4.23.5 CLI 警告）
- 现象：声明 `pip_dependencies` 的插件在**未装依赖的机器**上上传返回 200"已安装"，但加载阶段 `check_dependencies` 检测缺失跳过加载（`dependency_missing`），前端/API 全不可用且无明确阻断。
- 现状：Web/服务层安装解包前**硬拦截**缺 pip 依赖（preview 响应带 `pip_missing`，前端红字警示）；离线 CLI `install_plugin.py` 以 `[警告]` 输出未就绪原因 + `${python} -m pip install <pkg>`（不阻断，便于离线部署）；加载期把插件依赖与 pip 依赖**分开告警**并写明"已跳过加载（该插件不会出现在已加载插件中）"，`plugin_load_issues` 明细带修复命令（后台「未加载原因」照做即可）。
- 插件侧：README 仍应写明依赖；隔离测试前先装依赖。见 [plugin-authoring.md](plugin-authoring.md) §3。

### B2. `plugins/temp/` 无自动清理
- 现象：`_temp_files` 只记录无过期清理，上传临时文件只增不减。
- 插件侧 workaround：插件内对上传临时目录做定时清理（scheduler 任务）。
- 上报：建议框架补 `save_uploaded_file` 临时目录过期清理。

### B3. 无全局上传大小限制（观察点）
- 现象：框架无全局 `MAX_CONTENT_LENGTH`，大上传依赖插件自身校验。
- 插件侧 workaround：`save_uploaded_file`/`save_uploads` 内做双层大小/类型校验。
- 上报：可作为框架增强候选。

### B4. 插件内 `from .base_plugin import ...` 必加载失败（**已修复**：v4.23.3 文档纠正 + 定向提示 / v4.23.4）
- 现象：按"相对导入"编写的新插件，**安装成功**（`[OK] 安装完成`），但服务启动时
  `ERROR - 导入插件 plugins.<name>.<name> 失败: No module named 'plugins.<name>.base_plugin'`，
  插件随后从全局注册表消失：后台插件列表看不到、`/plugin/<name>` 404。
  **安装期零告警，只在启动期暴露**，极易误判为"装好了只是没生效"。
- 触发：主 .py 顶部写 `from .base_plugin import BasePlugin`。
- 根因：插件安装为 `plugins/<name>/` 子包（框架自动生成其 `__init__.py`），
  而 `base_plugin.py` 在**上级包** `plugins/base_plugin.py` → 相对导入解析到不存在的子模块。
- 现状（v4.23.3+）：
  - 开发指南 5 处错误示例已改为绝对导入，并新增导入说明（4.2）与"内置 `auth.py` 不是范本"提示；
  - **安装期**：主文件仅用相对导入 `base_plugin` 时立即 `warning` 告警（带绝对导入的 `try/except` 写法不误报）；
  - **启动期**：`import_error_hint` 对缺失 `<plugin>.base_plugin` 给出"改用绝对导入"的定向提示，并登记 `plugin_load_issues`（后台插件列表显示「未加载原因」，不再静默消失）。
- 插件侧：直接用绝对导入 `from plugins.base_plugin import BasePlugin`；同包辅助模块
  `from . import km_utils` / `from plugins.<name> import km_utils` 均可。
- 复现材料与完整分析：`KaleidoMini/docs/框架协调清单.md` FTK-KM-01。

## C. 框架侧缺陷（非插件触发，仅知悉）

- `core/network.py start_http_redirect` 不消费 POST body → 带 body 请求端口跳转被 RST（已修）。
- `core/frontend_tools.py migrate_legacy_config` 同路径误删配置（已修）。
- 后台 system 页 `loadQuota` 用未定义 `getCsrfToken` → 卡片数据未加载（已修，改 `_getCsrfCookie`）。
- `tools/package.py` 非 src_layout 分支曾漏排 pycache（已修 v4.21.1）。
- `tools/release.py bump` 版本替换锚点 bug（已修）。
- 全新环境缺 `tzdata` 启动即崩（已修，selfcheck 增加 zoneinfo 探测）。

## D. 提交协调清单的规范

凡在子插件开发中发现框架 bug/缺陷（无论是否已修复），按约定向主项目提交**可复现协调清单**：

1. **现象**：可观测行为（含 HTTP 状态码/错误/文件变化）。
2. **根因**：定位到模块/行（如 `core/plugin_pack.py::extract_plugin_pack`）。
3. **可复现场景**：最小步骤（含前置条件、curl/操作序列）。
4. **影响面与建议**：受影响对象 + 推荐修复方向。
5. 沉淀为 `wiki/lessons/` 页面并附复现场景；框架已修复的标注修复版本与 commit。
