# 插件编写规范

面向 FlaskToolkit 子项目的后端插件与前端工具的编写标准。权威完整版见框架 `documents/Flask-Plugin-Framework-Dev-Guide-v4.md`（第五章后端插件、第六章前端工具）；本文档为其可执行摘要，供 coding agent 直接落地代码。

## 1. 后端插件包结构

分发包（`.zip`）根目录扁平布局；安装解压时映射到 `plugins/<name>/`（v4.21 自包含目录化）。

```
<name>.zip
├── plugin.json          # 描述文件（必填，name 须与主 .py 同名）
├── <name>.py            # 主插件文件（必填）
├── <辅助>.py            # 可选：插件私有辅助模块
├── templates/           # 可选：页面模板 → 解压到 templates/plugins/<name>/
├── static/              # 可选：静态资源 → 解压到 templates/plugins/static/<name>/
├── locales/             # 可选：语言包 → 解压到 plugins/<name>/locales/
└── manifest.json        # 可选（强烈推荐）：完整性清单，由 tools/package.py 生成
```

映射关系：

| 包内路径 | 解压目标 |
| --- | --- |
| `<name>.py`（主/辅助模块） | `plugins/<name>/<basename>.py` |
| `plugin.json` | `plugins/<name>/<name>.json`（自动生成 `__init__.py`） |
| `templates/*` | `templates/plugins/<name>/*` |
| `static/*` | `templates/plugins/static/<name>/*` |
| `locales/*` | `plugins/<name>/locales/*` |

## 2. 插件基类继承与最简示例

> ⚠️ **导入必须用绝对路径 `from plugins.base_plugin import ...`，不要用 `from .base_plugin import ...`**
>
> 插件安装后是 `plugins/<name>/` **独立子包**（框架自动生成其 `__init__.py`），
> 而 `base_plugin.py` 位于**上级包** `plugins/base_plugin.py`。
> 因此相对导入会被解析成 `plugins.<name>.base_plugin`（不存在）→ `ModuleNotFoundError`。
>
> **最坑的地方**：安装阶段一切正常（`[OK] 安装完成`），只在**启动加载**时才报错，
> 且报错后插件直接从注册表消失（后台看不到、页面 404），排查成本很高。
> 实测：FlaskToolkit v4.23.2，见 known-framework-issues.md §B4。

```python
# ✅ 正确：与官方示例 examples/plugins/multitool_demo 一致
from plugins.base_plugin import BasePlugin
from plugins.base_plugin import permission as permission_required

# 兼容写法（若插件目录内自带 base_plugin.py 的另类布局）
try:
    from plugins.base_plugin import BasePlugin, permission as permission_required
except ImportError:
    from .base_plugin import BasePlugin, permission as permission_required


class MyPlugin(BasePlugin):
    name = "my_plugin"            # 插件标识（唯一，文件名须与之一致）
    title = "我的插件"             # 展示名称
    author = "Author"
    version = "1.0.0"
    category = "工具"
    description = "插件描述"
    permission = "user"            # 插件整体访问层级（public/user/admin）
    dependencies = []              # 依赖：插件名或第三方包名（支持版本约束）
    scheduled_tasks = []           # 定时任务配置

    routes = [
        {"path": "/api/hello", "methods": ["GET"], "view_func": hello_api},
    ]

    @permission_required("public")
    def hello_api(self):
        return self.success_response({"message": "Hello FlaskToolkit!"})
```

**同包内的辅助模块**（`<name>.py` 之外的 `km_*.py` 之类）两种写法都可行：
`from . import km_utils`（相对，推荐，v4.21 目录化后同属一个包）
或 `from plugins.<name> import km_utils`（绝对）。**唯独 `base_plugin` 必须绝对导入**。

## 3. plugin.json 字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `name` | 是 | 插件名，须与主 `.py` 文件名一致，且不在保留名黑名单 |
| `version` | 是 | 版本号（点分，支持 `v` 前缀）；update 须高于当前 |
| `title`/`author`/`category`/`description` | 否 | 展示元信息（覆盖插件类属性，两处须一致） |
| `permission` | 否 | `public`/`user`/`admin`（覆盖插件类） |
| `dependencies` | 否 | 依赖插件名列表，支持 `"auth>=2.0,<3"` 版本约束 |
| `pip_dependencies` | 否 | 第三方 pip 包列表（v4.10）；安装时不装，加载时检测缺失则跳过并标记 `dependency_missing` |
| `require_framework_version` | 否 | 最低框架版本（≤ 当前框架才可安装） |
| `capabilities` | 否 | 能力白名单声明（见第 7 节） |
| `icon` | 否 | 自定义 `.ico` 图标文件名（随 static/ 分发） |
| `repo`/`update_feed` | 否 | 市场铺路/插件级更新源元数据 |

## 4. 保留名黑名单

插件 `name` 不得为 `configs`/`data`/`temp`/`__pycache__`/`static`/`auth`/`user_manage`/`__init__`/`base_plugin`/`status`（`core/framework_manifest.py` 的 `PLUGIN_RESERVED_NAMES`），否则拒绝上传。

## 5. 描述一致性（关键：装不上）

`plugin.json` 与主 `.py` 插件类属性是**两份描述**，上传时框架经 AST 静态解析对齐校验：

- **name 三处一致**：`plugin.json.name` == 主 `.py` 文件名 == 插件类 `name`，任一不一致拒绝上传。
- **冲突字段拒绝**：`version`/`title`/`author`/`permission`/`category`/`description`/`dependencies`/`require_framework_version` 两处同时声明且不一致 → HTTP 400，报告具体冲突字段。
- **require_framework_version ≤ 当前框架版本** 才能安装；用新版框架能力须先 bump 框架。
- 常见坑：升级 `version` 只改了 plugin.json，忘了改 `.py` 里 `version = "1.0.0"` → 冲突被拒。

## 6. 权限三层

插件视图经 `@permission("public"/"user"/"admin")` 声明；未声明默认 `user`（需登录）。

| 值 | 含义 |
| --- | --- |
| `public` | 游客可直接访问 |
| `user` | 需登录 |
| `admin` | 仅管理员 |

- 插件页面 `/plugin/<name>` 默认需登录；声明 `public_page=True` 可豁免（如免登录工具/落地页）。
- 管理端接口 `/api/admin/*` 框架已默认强制管理员，插件无需也不应声明。

## 7. capabilities 能力声明（Deny by Default）

`capabilities` 为白名单授权（扁平字符串，语法 `域:子域:参数`），安装时与静态扫描交叉校验，`enforce` 模式下未声明行为拒绝安装。主要域：

| 域 | 语法示例 | 语义 |
| --- | --- | --- |
| filesystem | `filesystem:read:<path>` / `filesystem:write:<path>` | 路径前缀授权（目录含子内容） |
| network | `network:http:https://erp.corp.local/*` / `network:tcp:<host[:port]>` | HTTP 出站 / TCP/UDP；禁裸 `*` |
| network 监听 | `network:server:<host:port>` | bind/listen 监听端口（高风险） |
| webhook | `webhook:wecom:https://qyapi.weixin.qq.com/*` | 群机器人（wecom/dingtalk/feishu） |
| process | `process:exec` / `process:exec:<bin>` | 子进程；无参=任意（高危），带 bin=仅该可执行名 |
| scheduler | `scheduler` | 允许注册 APScheduler 定时任务 |
| database | `database:sqlite:<path>` / `database:mysql:<host:port/db>` | 数据库连接 |
| device | `device:serial:<port>` / `device:print` | 串口/打印 |
| framework | `framework:read` / `manage` / `core` | 操作框架核心文件三档；core≈root（高危，MIT 概不负责） |
| env | `env:read:<pattern>` | 环境变量读取 |
| storage | `storage:limit:<size>` | 存储配额（数字=MB，或带 mb/m/gb/g） |

**自属路径隐式豁免**（无需声明即可读写）：`plugins/configs/<name>.json`、`plugins/data/<name>/**`（`self.data_dir`/`get_data_path()`）、`plugins/temp/<name>/**`。

- `save_uploads` 落盘目录建议用相对路径并同步声明 `filesystem:write:<相对路径>`，否则 enforce 模式交叉校验报"未声明行为"拒绝。
- `shutil.rmtree` 为可约束 high：路径命中 `filesystem:write` 声明或行上 `# scan:ignore` 可豁免；`eval`/`exec`/`pickle.loads`/`subprocess`/`socket.bind` 等不可约束恒阻断。

## 8. BasePlugin 常用能力

| 方法/属性 | 说明 |
| --- | --- |
| `success_response(data)` / `error_response(msg, code)` | 统一返回 `{"code","message","data"}`，HTTP 状态码与 code 一致 |
| `validate_params(params)` | 参数校验，失败自动 400 |
| `save_uploaded_file(file_key='file')` | 保存上传（预检大小/类型），返回 `(临时路径, 原始文件名)` |
| `save_uploads(file_key='files', dest_dir=None, *, dedup, sanitize, max_upload_mb)` | 同步持久化上传助手，落盘到 `self.upload_dir` |
| `send_file_response(path, download_name=...)` | 下载响应（中文名 RFC 5987 编码、Range 断点） |
| `run_async_task(fn, *args)` / `get_async_task_status(task_id)` | 后台线程池异步任务 |
| `on_load()` / `on_ready()` / `on_shutdown()` / `on_unload()` / `on_uninstall()` | 生命周期钩子 |
| `on_event(event, handler)` / `emit_event(name, **data)` / `event_name(name)` | 事件总线（v4.16，跨插件松耦合） |
| `self.t()` / `self.get_lang()` / `self.available_langs()` | i18n 便捷方法（v4.21） |
| `load_config()` / `save_config()` | 自属配置读写 |

### 定时任务

```python
scheduled_tasks = [{"func": clean_cache, "trigger": "interval", "minutes": 30}]
```

### 页面路由（多模板，page=True）

```python
routes = [
    {"path": "/status", "name": "状态子页", "methods": ["GET"],
     "page": True, "template": "status.html", "view_func": self.page_status},
]
```

- 页面路由经 `/plugin/<name>/<sub_page>` 分发；`view_func` 返回 dict → 分发器渲染命名空间模板，返回 Response 则原样返回。
- 模板名恒为 `plugins/<name>/<template>`（正斜杠，Jinja 要求 POSIX 风格）。
- 主入口 `/plugin/<name>`：优先 `index.html`，回退 `<name>.html`；可用 `render_index()` 钩子提供上下文，或定义旧式 `page()`。
- 移动端独立模板放 `templates/plugins/<name>/mobile/`（同 URL，UA 分发，require ≥ 4.17.0）。

### 静态资源访问

```html
<link rel="stylesheet" href="/plugin-static/<name>/css/style.css">
```

## 9. 国际化（i18n）

模板文案用 `{{ t('...') }}`，须在插件自带 `locales/en.json` 等语言包登记词条；json 注意合法逗号/括号。插件语言包安装后自动合并（v4.21 起 `locales/` 进包）。

## 10. 前端工具开发规范

前端工具为 zip 包：`config.json`（必填）+ `<name>.html`（入口，文件名=name）+ 可选 `static/`。

```json
{
  "name": "my_tool",
  "version": "1.0.0",
  "category": "工具"
}
```

可选字段：`title`/`author`/`description`/`require_framework_version`/`permission`（默认 `public`）。

- 页面引入 `plugin_common.js` 获得统一鉴权与请求封装：`PluginCommon.request({url, method})`，自动注入 CSRF、401/403 跳转、业务结果以 `res.code` 判断。
- 静态资源经 `/frontend-static/<name>/<path>` 访问。
- 纯前端工具可不依赖后端 API（范式见内置 `password_generator`）。
- 前端工具权限在 `frontend_tools.json` 声明 `permission`，控制页面与静态资源访问。

## 11. require_framework_version 语义

- 值为"该插件依赖的框架最低版本"，用于 gate 安装与运行时加载。
- 用到的框架 API 引入版本要能覆盖：如 `get_data_path` ≥ 4.3.2、移动端独立模板 ≥ 4.17.0、事件总线 ≥ 4.16.0、目录化 `from plugins.<name> import <mod>` 与 `self.t()` ≥ 4.21.0。
- 提高 require 前先确认框架版本已 bump，否则无法安装端到端验证。
