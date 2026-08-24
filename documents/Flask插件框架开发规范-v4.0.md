# Flask插件框架开发规范

## 版本：v4.2（卸载清单 + 前端工具访问控制） | 更新日期：2026年08月24日

### 版本说明（v4.2 变更）
- **插件包卸载升级为 installed_files 清单机制**（5.6.6）：安装时把插件引入文件的相对路径清单写入 `plugins/<name>.json`，卸载按清单逐个删除（支持多 `.py` 插件包彻底卸载，无残留），无清单回退旧逻辑（兼容存量插件）。
- **前端工具访问控制**（4.6 / 6.5）：`/frontend/<name>` 页面与 `/frontend-static/` 静态资源按工具的 `permission` 字段做三层校验（`public`/`user`/`admin`，`auth` 未安装时全员放行）；上传/更新缺省 `permission=public`；新增改权限接口 `POST /api/admin/frontend/<name>/permission`；管理后台插件页提供前端工具权限下拉。
- **回归测试套件扩充至 16 脚本 306 项**（12 章）：新增 `test_plugin_cleanup.py`（卸载 installed_files 清单 + clean_old + 越界防御 23 项）、`test_frontend_permission.py`（前端工具三层权限 + 改权限 API + update 保留 permission 25 项）、`test_tools_ops.py`（backup/reset/config 运维工具 19 项）、`test_page_router.py`（大插件多模板页面路由 17 项），均隔离目录模式、已纳入 CI。
- **公共页面体验升级（8.1）**：首页新增搜索与排序（默认/热度/字母，热度取 API 调用与访问统计）；登录页支持记住用户名、显示/隐藏密码；首页/登录/登出/裸插件调试四页面样式统一为 `static/css/main.css` 设计体系，脚本抽离至 `static/js/`。
- **裸插件调试页增强（8.1）**：支持**路径参数**输入与替换（`<name>`/`<int:name>`，如 async_file_demo 的 `/status/<task_id>`）；**非安全方法自动携带 X-CSRF-Token**（修复带鉴权接口无法调试的 CSRF 403）；PUT/DELETE 改发 JSON body；展示 HTTP 状态/耗时/业务 code/实际 URL；结果一键复制与折叠、会话内请求历史。

### 版本说明（v4.1 变更）
- 后端插件分发改为**插件包（.zip）**机制：新增 5.6 节描述 plugin.json 描述文件、解压映射、静态资源访问与生命周期行为。
- 静态资源路由改为全局通配路由 `/plugin-static/<name>/<path>`（热加载友好），插件自定义 `static_dir` 仍受支持。
- 插件版本以 `plugin.json` 声明为准（落盘 `plugins/<name>.json`），扫描/目录指纹优先读取。
- 新增**最低框架版本要求** `require_framework_version`（非强制，一经声明须满足，否则拒绝安装/加载），见 5.7。
- 新增**内置插件**机制（`auth` / `user_manage`，`global_var.BUILTIN_PLUGINS`，不可卸载、受 Factory Reset 保护），见 5.8。
- 新增 **Factory Reset（重置）**能力：部分/全部还原至安装初始状态，见 5.9。
- 新增**管理后台**：`/admin/dashboard | plugins | logs | stats | system` 五页面（统一 `templates/admin/base.html` 布局 + `@admin_api` 权限保护）与系统信息接口 `GET /api/admin/system/info`，见 8.2 / 8.3。
- 新增回归测试套件（zip slip 专项、描述一致性、重载竞态、元信息端到端），见 11 章。
- `auth` 会话文件改为原子写（`.tmp` + `os.replace`），修复热加载重载时读到空文件的偶发 401 竞态。
- 新增**前端工具静态资源支持**：工具包 zip 内 `static/` 目录随包分发，经 `/frontend-static/<name>/<path>` 通配路由访问（安全解压 + zip slip 防护），见 6.1 / 6.4。
- 开启**模板自动重载**（`TEMPLATES_AUTO_RELOAD=True`）：前端工具/插件 html 更新后即时生效，无需重启服务。

### 版本说明

本版本基于 2026-08-22 完成的全栈重构（阶段一权限体系、阶段二安全加固、阶段三架构拆分）对齐更新，相比 v3.x 的主要变更：

- **权限模型正式化**：新增 `@permission("public"/"user"/"admin")` 装饰器，未声明接口默认"仅登录"；旧版 `require_role` 兼容。
- **鉴权与 CSRF**：登录后下发 HttpOnly `token` Cookie + 非 HttpOnly `csrf_token` Cookie，写请求需携带 `X-CSRF-Token` 头（前端由 `plugin_common.js` 自动注入）。
- **统一错误语义**：`error_response` 现返回对应 HTTP 状态码（此前 body 带 code 但 HTTP 恒 200），前端以 body.code 判断业务结果。
- **架构分层**：`app.py` 收敛为纯入口（149 行），服务逻辑拆入 `core/`，路由拆入 `routes/`；插件目录改由**内存注册表**提供，首页/管理页不再每次请求扫描磁盘。
- **运行配置环境变量化**：`FLASKTOOLKIT_HOST` / `FLASKTOOLKIT_PORT` / `FLASKTOOLKIT_DEBUG`。
- **生命周期钩子补齐**：新增 `on_unload()` / `on_uninstall()`（与原有 `on_load()` / `on_shutdown()` 对齐）。

---

## 一、框架特性概览

- **插件化**：后端插件包（`.zip`，含 plugin.json 描述文件 + 主 `.py` + 可选 templates/static）与前端工具（HTML 包）均可动态上传/更新/卸载/启用/禁用。
- **可选鉴权**：`auth` 是可选插件——不安装时系统全员放行；安装后按三层权限控制。
- **三层权限**：游客（public）/ 仅登录（user）/ 仅管理员（admin），由插件通过装饰器自行声明。
- **热重载**：文件监听自动增量重载插件与前端工具，无需重启服务。
- **定时任务**：插件可声明 `scheduled_tasks`，框架自动注册到调度器（Asia/Shanghai 时区）。
- **统计与日志**：API 调用统计、前端工具访问统计自动累积；分级日志落盘。

---

## 二、项目结构（重构后）

```
FlaskToolkit/
├── app.py                     # 入口：初始化、加载用户配置与启动自检、register_routes(app)、关闭钩子
├── global_var.py              # 纯路径常量 + 共享状态 + 用户配置（CONFIG_ITEMS / load_user_config）
├── requirements.txt           # 运行依赖（版本锁定）
├── requirements-dev.txt       # 开发/测试依赖
├── core/                      # 服务层（不依赖 app 实例）
│   ├── permission.py          #   统一权限体系（@permission 解析 / 三层校验 / CSRF 双提交）
│   ├── plugin_loader.py       #   插件加载器（依赖校验 / 拓扑排序 / 按序加载）
│   ├── plugin_cache.py        #   插件发现缓存（目录/文件指纹 + 状态快照）
│   ├── plugin_pack.py         #   插件包（.zip）解析与安装
│   ├── plugin_status.py       #   插件启用/禁用状态读写
│   ├── watcher.py             #   文件监听（增量缓存 + 热重载）
│   ├── frontend_tools.py      #   前端工具配置加载
│   ├── stats.py               #   调用统计读写
│   ├── audit.py               #   审计日志（JSONL 追加 data/audit.log）
│   ├── package_sign.py        #   插件包完整性校验（manifest 哈希清单 + RSA 签名）
│   ├── factory_reset.py       #   工厂重置（部分/全部 scope）
│   ├── selfcheck.py           #   启动完整性自检
│   ├── logging_setup.py       #   日志配置 + 插件日志适配器
│   └── utils.py               #   通用工具（端口、路径参数、上传大小校验、跨插件调用等）
├── routes/                    # 路由层（register(app) 注入）
│   ├── interceptor.py         #   全局请求拦截器（系统级兜底鉴权）
│   ├── public.py              #   公开页面 / 错误处理器
│   ├── plugin.py              #   插件页面 / API 分发
│   ├── frontend.py            #   前端工具页面 + 管理 API
│   └── admin.py               #   插件管理 API / 统计 / 日志 / 审计
├── plugins/                   # 插件目录
│   ├── base_plugin.py         #   插件基类 + @permission 装饰器 + 生命周期钩子
│   ├── auth.py                #   可选鉴权插件（PBKDF2 / HttpOnly Cookie + CSRF）
│   └── user_manage.py         #   内置用户管理插件（BUILTIN，受 Factory Reset 保护）
├── examples/                  # 官方示例插件/工具包（6 个）+ install_all.py 一键安装
├── tools/                     # 开发运维命令行工具（python tools/xxx.py）
│   ├── config.py              #   配置管理 CLI（show/set/unset/reset/check/env）
│   ├── package.py             #   插件包打包/签名/校验 CLI（genkey/pack/verify/show）
│   ├── backup.py              #   手动备份/恢复工具（Factory Reset 前备份关键数据）
│   └── reset.py               #   深度重置工具（服务停止时使用，绕过运行时文件锁定）
├── tests/                     # 回归测试套件（16 脚本 306 项 + 端到端链路验证）
├── templates/                 # 页面模板（首页/登录/错误码页 400-500/admin 管理后台/插件页）
│   ├── admin/                 #   管理后台（dashboard / plugins / logs / stats / system）
│   ├── frontend_tools/        #   前端工具模板
│   └── plugins/               #   插件页面模板
├── static/                    # 静态资源（css/main.css 统一设计体系 + error.css 错误页；js/plugin_common.js 统一鉴权前端 + main.js 公共脚本 + index/login/plugin_default/logout 页面脚本）
├── .github/workflows/ci.yml   # GitHub Actions CI 工作流
├── data/                      # 运行时数据（统计/审计/用户配置，已 gitignore）
├── logs/                      # 运行日志（已 gitignore）
├── documents/                 # 开发规范 / Roadmap / CI 上手指南
├── LICENSE                    # MIT 许可
├── CONTRIBUTING.md            # 贡献指南
└── .gitignore                 # 运行时数据与归档文档忽略规则
```

---

## 三、快速开始

### 3.1 环境准备

```bash
pip install -r requirements.txt
```

### 3.2 启动服务

```bash
python app.py
```

### 3.3 运行环境变量

| 变量 | 默认值 | 说明 |
|------|-------|------|
| `FLASKTOOLKIT_HOST` | `127.0.0.1` | 绑定地址；默认仅本机访问，局域网访问设 `0.0.0.0` |
| `FLASKTOOLKIT_PORT` | 自动探测 | 显式指定端口；被占用自动回落探测可用端口 |
| `FLASKTOOLKIT_DEBUG` | 关闭 | 调试模式（`1`/`true`/`yes`/`on` 开启），生产勿开 |

```bash
FLASKTOOLKIT_HOST=0.0.0.0 FLASKTOOLKIT_PORT=8000 python app.py
```

---

## 四、权限模型（v4.0 核心）

### 4.1 三层权限

| 层级 | 装饰器 | 说明 |
|------|--------|------|
| 游客 | `@permission("public")` | 不要求登录（登录/登出、公开信息） |
| 仅登录 | `@permission("user")` | 需登录（默认兜底） |
| 仅管理员 | `@permission("admin")` | 需登录且角色为 admin |

### 4.2 声明方式

权限由插件在路由方法上**自行声明**，框架在请求进入时统一校验：

```python
from .base_plugin import BasePlugin
from .base_plugin import permission as permission_required  # 注意别名！

class MyPlugin(BasePlugin):
    @permission_required("public")
    def login(self):
        return self.success_response("游客可访问")

    @permission_required("user")   # 或省略装饰器（默认仅登录）
    def info(self):
        return self.success_response("仅登录可访问")

    @permission_required("admin")
    def config(self):
        return self.success_response("仅管理员可访问")
```

### 4.3 兼容旧版

旧版 `require_role("user"/"admin")` 标记会被框架统一识别，无需改动即可继续工作。

### 4.4 重要：命名遮蔽陷阱

`permission` 既是模块级装饰器又是插件类属性。插件类内若声明 `permission = "admin"`（声明插件访问层级），**会遮蔽类体中的 `@permission(...)`**（被解析为字符串）。因此装饰器必须用别名导入：

```python
from .base_plugin import permission as permission_required
```

### 4.5 可选鉴权（auth 未安装）

`auth` 插件未安装时，系统处于**无鉴权模式**：所有请求放行、所有工具可见。安装 `auth` 插件后立即启用三层权限校验。

### 4.6 前端工具访问控制（v4.2 新增）

前端工具（页面与静态资源）同样按 `permission` 字段做三层校验（`public`/`user`/`admin`，默认 `public`），与 API 权限模型一致、共用同一套校验逻辑；`auth` 未安装时全员放行。详见 6.5。

---

## 五、后端插件开发规范

### 5.1 插件基类继承

```python
from .base_plugin import BasePlugin
from .base_plugin import permission as permission_required

class MyPlugin(BasePlugin):
    name = "my_plugin"            # 插件标识（唯一，文件名需与之一致）
    title = "我的插件"             # 展示名称
    author = "Author"
    version = "1.0.0"
    category = "工具"
    description = "插件描述"
    permission = "user"            # 插件整体访问层级（用于首页展示过滤）
    dependencies = []              # 依赖：插件名或第三方包名
    scheduled_tasks = []           # 定时任务配置
```

### 5.2 最简插件示例

```python
from .base_plugin import BasePlugin
from .base_plugin import permission as permission_required


class HelloPlugin(BasePlugin):
    name = "hello"
    title = "Hello 插件"
    author = "Author"
    version = "1.0.0"
    category = "示例"
    description = "最简插件示例"

    routes = [
        {"path": "/api/hello", "methods": ["GET"], "view_func": hello_api},
    ]

    @permission_required("public")
    def hello_api(self):
        return self.success_response({"message": "Hello FlaskToolkit!"})
```

### 5.3 生命周期钩子（v4.0 补齐）

| 钩子 | 触发时机 | 默认实现 |
|------|---------|---------|
| `on_load()` | 插件加载完成后 | 空 |
| `on_shutdown()` | 服务停止前 | 空 |
| `on_unload()` | 插件卸载前（显式卸载） | 空 |
| `on_uninstall()` | 插件删除前（显式卸载） | 空 |

```python
def on_load(self):
    """初始化资源、连接数据库等"""
    self.logger.info("插件已加载")

def on_shutdown(self):
    """服务停止前的清理"""
    self.save_state()

def on_unload(self):
    """卸载前的清理（框架默认空实现，可重载）"""
    pass

def on_uninstall(self):
    """删除前的最终清理（框架默认空实现，可重载）"""
    pass
```

### 5.4 定时任务

```python
def clean_cache(self):
    ...

scheduled_tasks = [
    {"func": clean_cache, "trigger": "interval", "minutes": 30},
]
```

### 5.5 路径参数与参数校验

路由支持 `<param>` 路径参数，框架自动解析传递：

```python
{"path": "/api/items/<item_id>", "methods": ["GET"], "view_func": get_item}

def get_item(self, item_id):
    return self.success_response({"item_id": item_id})
```

可在 `validate_params` 中定义参数校验，失败自动返回 400。

### 5.5.1 大插件多模板（页面路由 page=True，v4.2 新增）

当后端插件需要**多个 HTML 模板**（主模板作入口 + 其它模板作功能分担或静态页）时，可通过**页面路由** + **模板命名空间**实现，聚焦大插件（多资源 + 多模块 + 多模板，但同名主入口一定存在）：

**① 模板命名空间 `templates/plugins/<name>/`**

插件包解压时，zip 内 `templates/xxx`（带或不带 `<name>/` 前缀）统一落位到 `templates/plugins/<name>/`，避免多插件模板名冲突（见 5.6.4 解压映射）。插件模板名恒为 `plugins/<name>/<template>`（**正斜杠**，Jinja 模板名须为 POSIX 风格；框架已自动归一化反斜杠）。

**② 页面路由声明 `"page": True`**

在 `routes` 中声明页面路由，条目不进 API 分发，由通配路由 `/plugin/<name>/<path:sub_page>` 分发（启动时注册一次，热加载友好）：

```python
{"path": "/status", "name": "状态子页", "methods": ["GET"],
 "page": True, "template": "status.html", "view_func": self.page_status},
{"path": "/user/<username>", "name": "用户子页", "methods": ["GET"],
 "page": True, "template": "user.html", "view_func": self.page_user},
```

- 未声明 `template` 时默认取路径末段 + `.html`（如 `/about` → `about.html`）；
- `view_func` 返回 **dict** → 分发器渲染命名空间模板（dict 作为上下文）；返回 **Response**（如 `self.render(...)`）→ 原样返回；
- 路径参数 `<param>`/`<int:param>` 自动注入 `kwargs`（复用 `parse_path_pattern`）。

**③ 主入口与渲染助手**

- 主入口 `/plugin/<name>`：优先 `index.html`，回退 `<name>.html`；`render_index()` 钩子返回上下文 dict（默认 `{}`，模板可经 `plugin` 对象访问属性）；
- 插件类**定义了 `page()`**（旧式自定义入口，基类无此方法）时优先调用 `page()`，兼容存量插件；
- `self.render(template, **context)`：自动定位命名空间（回退旧式 `plugins/<template>`），返回 `Response`，视图函数可直接 `return self.render(...)`；
- 无任何自定义主入口时回退裸插件调试页（见 8.1）。

**④ 示例**：`hello_plugin` 展示主入口 `page()` + 子页 `about`/`usage`/`greet/<name>`（路径参数）；`multitool_demo` 完整演示大插件三要素（多模板 + 辅助 .py multitool_utils + 静态资源 css/js，含文本分析 API）；`tests/test_page_router.py` 17 项固化页面路由回归。

### 5.6 插件包（.zip）分发规范（v4.0 新增）

后端插件以**插件包**（`.zip`）形式上传与分发（类比前端 `.zip` 工具包），不再上传单个 `.py` 文件——插件可能携带模板与静态资源，必须随包整体分发。

#### 5.6.1 包结构

```
<plugin_name>.zip
├── plugin.json          # 描述文件（必填，类比前端 config.json）
├── <plugin_name>.py     # 主插件文件（必填，文件名须与 plugin.json 的 name 一致）
├── templates/           # 可选：插件专属模板 → 解压到 templates/plugins/
├── static/              # 可选：静态资源 → 解压到 templates/plugins/static/<name>/
└── manifest.json        # 可选（强烈推荐）：完整性校验清单，由 tools/package.py 生成，见 10.4
```

#### 5.6.2 plugin.json 字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | 是 | 插件名，须与主 `.py` 文件名一致 |
| `version` | 是 | 版本号（点分数字，支持 `v` 前缀）；update 时须高于当前版本，否则拒绝 |
| `title` | 否 | 显示名称（覆盖插件类 `title`） |
| `author` | 否 | 作者（覆盖插件类 `author`） |
| `category` | 否 | 分类 |
| `description` | 否 | 描述 |
| `permission` | 否 | 权限级别（覆盖插件类 `permission`） |
| `dependencies` | 否 | 依赖插件名列表（如 `["auth"]`） |
| `require_framework_version` | 否 | 最低框架版本要求（点分版本，如 `"4.0.0"`）；非强制，一经声明须满足，见 5.7 |

版本以 `plugin.json` 声明为准：上传/更新后描述文件落盘为 `plugins/<name>.json`，插件扫描与目录指纹均优先读取该文件，保证 catalog 显示版本与包内声明一致。

#### 5.6.3 描述一致性（plugin.json 与插件类属性对齐）

`plugin.json` 与主 `.py` 内的插件类属性是**两份描述**（字段见 5.6.2），上传/更新时框架通过 AST 静态解析主 `.py`（不执行插件代码）做对齐校验：

| 规则 | 说明 |
|------|------|
| name 三处一致 | `plugin.json.name` == 主 `.py` 文件名 == 插件类 `name`（AST 可提取时），任一不一致拒绝上传 |
| 冲突字段拒绝 | `version`/`title`/`author`/`permission`/`category`/`description`/`dependencies`/`require_framework_version` 两处同时声明且不一致 → 拒绝并报告具体冲突字段 |
| 缺失补全 | `plugin.json` 缺失字段回退插件类属性（`version` 缺失用类兜底并告警） |
| 对齐落盘 | 对齐后的完整描述落盘为 `plugins/<name>.json`，为运行时唯一权威 |

> **对开发者**：修改插件元信息（版本/标题/权限等）时，需同步更新 `plugin.json` 与插件类属性，否则上传/更新会被拒绝。
>
> 运行时插件扫描以落盘描述文件为权威（缺失字段保留类属性兜底，兼容存量无描述文件插件）；若描述文件 `name` 与类 `name` 不一致则跳过加载并报错。

#### 5.6.4 解压映射

| 包内路径 | 解压目标 |
|---------|---------|
| `<name>.py` | `plugins/<name>.py` |
| `plugin.json` | `plugins/<name>.json` |
| `templates/*` | `templates/plugins/*` |
| `static/*` | `templates/plugins/static/<name>/*` |

解压内置 **zip slip 路径穿越防护**：拒绝 `..`、绝对路径、盘符路径条目（基于 zip 内 `/` 分隔的纯字符串检查，不依赖平台分隔符）。

#### 5.6.5 静态资源访问

插件模板中通过全局通配路由 `/plugin-static/<name>/<path>` 访问静态资源（启动时注册一次，运行时按插件名分发，热加载友好）：

```html
<link rel="stylesheet" href="/plugin-static/user_manage/css/user_manage.css">
```

#### 5.6.6 生命周期行为

- **上传**：校验描述文件 + 主 `.py` 文件名一致性 → 安全解压 → 自动加载（`load_plugins`）。
- **更新**：校验包内插件名与目标一致 + 新版本必须高于当前版本 → 覆盖解压 → 重载。
- **卸载**：按安装时写入 `plugins/<name>.json` 的 `installed_files` 清单（相对路径）逐个删除插件引入的文件（主 `.py`、辅助 `.py` 模块、描述文件、模板、静态资源），并清理残留空目录；老插件无清单时回退为删除主 `.py`、描述文件 `plugins/<name>.json`、`templates/plugins/<name>.html` 与 `templates/plugins/static/<name>/` 目录。

#### 5.6.7 Demo：UserManage 插件包

参考 `C:\Users\Admin\Desktop\UserManage` 目录：

```
UserManage/
├── plugin.json              # name=user_manage, version=1.0.1, permission=admin, dependencies=["auth"], require_framework_version=4.0.0
├── user_manage.py           # 主插件
├── templates/
│   └── user_manage.html     # 页面模板
└── static/
    └── css/
        └── user_manage.css  # 静态资源（含 .plugin-static-badge 徽章样式）
```

打包命令：`UserManage-v1.0.1.zip`（zip 根目录直接包含上述文件）。上传后在管理页即可看到该插件，访问 `/plugin/user_manage` 渲染页面，静态资源经 `/plugin-static/user_manage/...` 正常加载。

---

### 5.7 最低框架版本要求（require_framework_version）

后端插件可声明 `require_framework_version`（`plugin.json` 或插件类属性，非强制），用于声明插件所需的最低框架版本，以支撑框架持续迭代：

- **未声明**：不检查，任意框架版本可用。
- **声明了**：上传/更新时与 `global_var.FRAMEWORK_VERSION`（当前 `4.1.0`）做点分版本比较（`compare_versions`，修复了前端工具原先字符串比较的缺陷）；插件要求高于框架版本 → 拒绝安装并报告。
- **运行时双重校验**：`load_plugins` 加载时同样校验（防止手工放置插件绕过上传校验），不满足则跳过加载并报错。
- 参与描述一致性对齐（冲突拒绝/缺失补全），见 5.6.3。

```json
// plugin.json 示例：要求框架 ≥ 4.0.0
{"name": "user_manage", "version": "1.0.1", "require_framework_version": "4.0.0"}
```

### 5.8 内置插件（Builtin）

框架内置随系统分发、不可卸载的插件（`global_var.BUILTIN_PLUGINS`）：

| 插件 | 说明 |
|------|------|
| `auth` | 认证/会话/权限（可选插件，但作为内置分发；未安装时游客模式放行） |
| `user_manage` | 用户管理（作为内置插件，同时充当插件包机制的官方演示） |

- **受保护**：管理页插件列表展示内置徽标；卸载接口拒绝删除内置插件；Factory Reset 的 `plugins` 范围跳过内置插件。
- **随框架分发**：内置插件的 `.py`、描述文件、模板与静态资源随项目存放，加载方式与其他插件一致。
- **默认账号**：`auth` 在无用户配置时自动重建默认管理员 `admin/admin123`（可被 Factory Reset 的 `builtin` 范围重置）。
- **权限模型不变**：内置插件同样通过装饰器声明三层权限（游客/登录/管理员）。

### 5.9 Factory Reset（重置）

将部分/全部框架数据还原至安装初始状态。接口 `POST /api/admin/factory-reset`（管理员权限，body 带 `X-CSRF-Token`），请求体 `scope`：

| 值 | 重置内容 |
|------|---------|
| `"all"` | 全部（下列所有范围 + 内置配置） |
| `"plugins"` | 清除全部非内置插件（.py / 描述文件 / 模板 / 静态资源 / 临时目录），内置插件受保护 |
| `"frontend_tools"` | 清除前端工具（清单 + 模板目录） |
| `"stats_logs"` | 清除调用统计 `data/stats.json`（含内存统计）与日志 `logs/` |
| `"sessions"` | 清除登录会话 `plugins/data/sessions.json` |
| `"temp"` | 清除运行产生的临时文件（`.plugin_cache`、`__pycache__`、`temp/`、`plugins/temp/`） |

`scope` 也可传列表（如 `["sessions", "stats_logs"]`）仅重置指定范围。说明：

- `builtin` 范围仅在 `all` 时执行：重置内置插件配置（`auth` 恢复默认 `admin/admin123`）。
- 重置后自动重载插件（内置插件按默认配置重新加载）。
- 删除操作逐项容错，返回 `cleaned`/`failed` 列表（受限环境删除失败不影响接口返回）。

```json
// 请求
{"scope": "all"}
// 响应
{"code": 200, "data": {"cleaned": ["登录会话", ...], "failed": []}, "message": "重置完成"}
```

---

## 六、前端工具开发规范

### 6.1 工具包格式

前端工具为 zip 包，至少包含入口文件与描述文件，**可选携带 `static/` 静态资源目录**（CSS/JS/图片等，随包分发）：

```
my_tool.zip
├── config.json           # 元信息配置（必填）
├── my_tool.html          # 入口页面（文件名 = name.html，必填）
├── static/               # 可选：静态资源 → 解压到 templates/frontend_tools/static/<name>/
│   ├── css/style.css
│   └── js/app.js
└── manifest.json        # 可选（强烈推荐）：完整性校验清单，由 tools/package.py 生成，见 10.4
```

`config.json` 必填字段：

```json
{
    "name": "my_tool",
    "version": "1.0.0",
    "category": "工具"
}
```

可选字段：`title`、`author`、`description`、`require_framework_version`、`permission`（默认 `public`，访问控制见 6.5）。

### 6.2 使用 plugin_common.js

前端工具页面引入 `plugin_common.js` 获得统一鉴权与请求封装：

```html
<script src="/static/js/plugin_common.js"></script>
<script>
    PluginCommon.request({
        url: '/api/hello',
        method: 'GET'
    }).then(res => {
        if (res.code === 200) { /* 成功 */ } else { /* 业务错误 */ }
    }).catch(err => { /* 网络错误或未登录 */ });
</script>
```

- `request()` 自动注入 `X-CSRF-Token` 头（从 `csrf_token` Cookie 读取）。
- HTTP 401 自动跳转登录页、403 跳转 403 页。
- 业务结果以 **`res.code`** 判断（而非 HTTP 状态码）。

### 6.3 静态资源访问

工具包内 `static/` 目录的文件在**上传/更新时安全解压**到 `templates/frontend_tools/static/<tool_name>/`，页面通过全局通配路由访问（热加载友好，新增工具无需重启）：

```html
<link rel="stylesheet" href="/frontend-static/<tool_name>/css/style.css">
<script src="/frontend-static/<tool_name>/js/app.js"></script>
```

- 路由 `/frontend-static/<tool_name>/<path>` 由框架统一注册，`send_from_directory` 提供路径穿越防护；工具不存在或静态目录缺失返回 404。
- 上传/更新采用**安全解压**：内置 **zip slip** 路径穿越防护（拒绝 `..`、绝对路径、盘符路径），入口 `config.json`/未知条目忽略。
- 更新时**先清理旧 `static/<name>/` 目录再解压**，避免残留旧版本静态文件（清理失败不阻塞本次更新，仅记录警告）。
- 卸载时删除入口 html 与 `static/<name>/` 目录。

### 6.4 内置示例：随机密码生成器

框架内置前端工具示例 **随机密码生成器**（`password_generator`），作为开发者参考模板：

- 位置：`templates/frontend_tools/password_generator.html`，已在 `frontend_tools.json` 注册（分类：安全工具）。
- 访问：`/frontend/password_generator`（首页卡片入口）。
- 功能：密码长度 6-64、四类字符集勾选、排除易混淆字符（`0O1lI|`'".,`）、批量生成 1-10 个、密码学安全随机（`crypto.getRandomValues`）、强度分级（熵 ≥100 极强 / ≥70 强 / ≥45 中 / 否则弱）、一键复制（`navigator.clipboard` + 降级方案）。
- 纯前端实现：**不调用任何后端 API、不上传数据**，仅本地生成，可作为不依赖后端的静态前端工具范式；若前端工具需要调用后端接口，按 6.2 引入 `plugin_common.js`。

### 6.5 前端工具访问控制（v4.2 新增）

每个前端工具在 `frontend_tools.json` 中声明 `permission` 字段（`public` / `user` / `admin`），控制页面与静态资源的访问：

| 值 | 含义 |
|------|------|
| `public`（默认） | 游客可直接访问 |
| `user` | 需登录；未登录访问页面/静态资源跳转登录页（携带 redirect） |
| `admin` | 仅管理员；普通用户访问返回 403 页，未登录跳转登录页 |

- 页面路由 `/frontend/<name>` 与静态资源路由 `/frontend-static/<name>/<path>` 均做该校验（与 API 共用 `core/permission._check_permission` 统一逻辑）。
- `auth` 插件未安装时全员放行（可选鉴权），与 API 权限模型一致。
- 上传/更新时工具缺省 `permission=public`；`frontend_tools.json` 可声明 `permission` 覆盖（内置密码生成器已改为 `public`）。
- 修改权限：管理后台「插件管理 → 前端工具」权限下拉，或调用管理接口：

```
POST /api/admin/frontend/<name>/permission
Content-Type: application/json
X-CSRF-Token: <csrf_token>
{"permission": "admin"}   # 仅接受 public / user / admin
```

---

## 七、API 接口规范

### 7.1 通用返回格式

```json
{"code": 200, "message": "操作成功", "data": {...}}
```

### 7.2 成功响应

```python
return self.success_response({"key": "value"})
# → {"code": 200, "message": "操作成功", "data": {"key": "value"}}   (HTTP 200)
```

### 7.3 错误响应（v4.0：HTTP 状态码与 body.code 一致）

```python
return self.error_response("操作失败", 400)
# → {"code": 400, "message": "操作失败", "data": null}   (HTTP 400)
```

`error_response(message, code)` 现返回**对应 HTTP 状态码**（此前 HTTP 恒 200）。前端请统一以 body.code 判断业务结果。

### 7.4 参数校验

```python
def validate_params(self, params):
    errors = []
    if 'username' not in params:
        errors.append('缺少 username')
    return {}, errors
```

### 7.5 常见错误码一览

框架统一了 API 错误语义与错误页面风格。**HTTP 状态码与 body.code 一致**，前端以 `res.code` 判断业务结果。

| HTTP / code | 含义 | API 返回示例 | 页面表现 |
|------------|------|-------------|---------|
| `200` | 成功 | `{"code": 200, "message": "操作成功", "data": ...}` | 正常渲染 |
| `400` | 参数错误 / 校验失败 | `{"code": 400, "message": "缺少 username", "data": null}` | 400 错误页 |
| `401` | 未登录 / 会话过期 | `{"code": 401, "message": "未登录或登录已过期"}` | 页面跳转登录页 |
| `403` | 权限不足 / CSRF 失败 | `{"code": 403, "message": "需要管理员权限"}` | 403 错误页 |
| `404` | 资源不存在（插件未加载/路径错误） | `{"code": 404, "message": "API路径 /xxx 不存在"}` | 404 错误页 |
| `405` | 请求方法不支持 | `{"code": 405, "message": "不支持的请求方法 ..."}` | 405 错误页 |
| `500` | 服务器内部错误 | `{"code": 500, "message": "接口调用失败: ..."}` | 500 错误页 |

- API 错误响应统一走 `error_response(message, code)`，HTTP 状态码与 body.code 一致。
- 页面错误统一使用 `templates/*.html`（400/401/403/404/405/500），共享 `static/css/error.css` 统一设计风格。
- 401 在页面场景下自动携带 `redirect` 参数跳转登录页；403 可跳转 `/403?message=...` 展示具体原因。

---

## 八、路由规则与路径规范

- 插件 API 统一走 `/api/<plugin_name>/<path>` 分发（由框架 `routes/plugin.py` 处理）。
- 插件页面统一走 `/plugin/<plugin_name>`。
- 管理端接口（`/api/admin/*`）框架已默认强制管理员权限，插件无需也不应声明。
- 未加载/已禁用的插件访问返回 404（非 500）。

### 8.1 公共页面（首页 / 登录 / 登出 / 裸插件调试）

公共页面共享 `static/css/main.css` 统一设计体系（以首页风格为准：深色导航栏、主色蓝 `#3498db`、成功绿 `#27ae60`、卡片圆角）与 `static/js/main.js` 公共脚本（`FT.getCookie` / `FT.checkAuth` / `FT.doLogout`）：

| 页面 | 路径 | 功能 |
|------|------|------|
| 首页 | `/` | 工具卡片按分类展示；工具条支持**搜索**（名称/描述/作者/分类实时过滤）与**排序**（默认/热度/字母，分类内排序）；热度=后端插件 API 调用总数、前端工具访问数（渲染时注入 `data-heat`） |
| 登录 | `/login` | 记住用户名（localStorage）、显示/隐藏密码、回车提交、防重复提交、登录成功页 + redirect 安全回跳（拒绝站外与 `/login` 自身） |
| 登出 | `/logout` | 调用登出接口清理 Cookie + 成功页（自动/手动跳转登录） |
| 裸插件调试 | `/plugin/<name>`（无自定义模板时） | 列出插件全部 API 与参数（string/boolean/file/array/object **+ 路径参数 `<name>`/`<int:name>` 输入框**），可视化调用并展示 JSON 结果（**HTTP 状态码/耗时/业务 code/实际请求 URL**）；**非安全方法自动携带 CSRF**；**PUT/DELETE 与 POST 一致发 JSON body**；一键复制/折叠结果、请求历史；属插件测试工具，功能改动需谨慎 |

### 8.2 管理后台页面

管理后台提供前端页面管理 FlaskToolkit 应用（入口 `/admin/dashboard`，首页右上角「🛠️ 管理后台」按钮），统一继承 `templates/admin/base.html` 布局（顶部导航：仪表盘/插件管理/日志/统计/系统管理 + 用户信息 + 退出登录），**所有页面路由加 `@admin_api` 保护**（未登录 302 跳登录页携带 redirect、普通用户渲染 403 页、auth 未安装时放行）：

| 页面 | 路径 | 功能 |
|------|------|------|
| 仪表盘 | `/admin/dashboard` | 统计卡片 + 系统信息 + 快捷入口 + 内置插件列表 |
| 插件管理 | `/admin/plugins` | 上传/更新/卸载/启用/禁用/配置/全部重置 |
| 日志 | `/admin/logs` | 按级别与行数查看日志、按插件过滤 |
| 统计 | `/admin/stats` | API 调用 Top100（可搜索）+ 前端访问 Top100 |
| 系统管理 | `/admin/system` | 系统信息 + Factory Reset 分 scope 勾选 / 全部重置（见 5.9） |

### 8.3 管理端接口

- `GET /api/admin/system/info`：框架版本、内置插件列表、Python/平台版本、base_dir、host、debug 标志与各类统计数（仪表盘与系统页数据源）。
- `GET /api/admin/stats`：插件数（含 catalog）、前端工具数、API 调用与前端访问统计明细。
- `GET /api/admin/logs`：按 `level`/`lines`/`plugin` 读取日志；级别白名单（非法值回退 info），级别映射到 `app.log`（INFO+）与 `error.log`（ERROR+），warning/critical 按行内 ` - LEVEL - ` 标记二次过滤。

---

## 九、常见问题

### 9.1 插件 API 返回 404

- 插件未加载：检查是否启用、依赖是否满足。
- 路径不匹配：确认 `routes` 中 path 与请求一致（含参数格式）。

### 9.2 写请求返回 403 CSRF 校验失败

- 前端必须引入 `plugin_common.js` 或手动注入 `X-CSRF-Token` 头（值 = `csrf_token` Cookie）。
- GET/HEAD/OPTIONS 不需要 CSRF 头。

### 9.3 插件接口 401 未登录

- 接口未声明 `@permission_required("public")` 时默认"仅登录"，未登录访问返回 401 并跳转登录页。

### 9.4 登录失败提示"用户名或密码错误"

- auth 插件默认管理员 `admin / admin123`，可在 `plugins/configs/auth.json` 修改。

---

## 十、插件信任模型与安全

### 10.1 信任模型（重要）

**插件即代码**：后端插件（`plugins/*.py`）与前端工具（HTML/JS/CSS）被框架**直接加载执行**，运行在 Flask 服务进程内，拥有与框架等同的文件系统与网络权限，**无沙箱隔离**。

因此：
- **安装插件即信任其作者**。只应安装来源可信、经过审查的插件包。
- 管理后台「插件管理」页安装/更新/启用插件前，请确认插件包来源与内容。
- 框架不对插件行为做运行时隔离；插件导致的任何数据/安全影响由安装者自行承担。

### 10.2 上传大小限制

- 管理后台上传的**后端插件包**与**前端工具包**统一受 `global_var.PACKAGE_MAX_UPLOAD_SIZE`（默认 10MB）限制，超限返回 `413 Payload Too Large`。
- 插件自身提供的「数据上传」接口大小由插件通过 `BasePlugin.max_upload_size` 自行约束（默认 10MB）。

### 10.3 Factory Reset（恢复出厂设置）

- 设计意图：将部分/全部框架数据还原至安装初始状态，**不提供自动备份**（数据丢失由用户自行承担）。
- **此操作不可逆**：执行前请务必手动备份关键数据（`plugins/configs/`、`data/`、`frontend_tools.json` 等）。
- 管理后台重置弹窗已内置「不可撤销、请先备份」的风险提示，确认后才会执行。
- 内置插件（`auth`、`user_manage`）在重置中受保护不被删除；`all` 范围会重置其配置（auth 恢复默认 `admin/admin123`）。

### 10.4 插件包完整性校验与签名（方案C）

`manifest.json`（可选但强烈推荐，位于包根目录）记录包内全部成员的 sha256，随包分发：

```json
{
    "schema_version": "1.0",
    "package_type": "backend",
    "files": {"plugin.json": "sha256...", "my_plugin.py": "sha256...", "static/css/x.css": "..."},
    "signature": {"algorithm": "RSA-SHA256", "value": "base64...", "signer": "张三"}
}
```

- **完整性**：安装时对包内除 manifest 外的全部成员逐文件比对哈希，防篡改/损坏/zip slip 错位/加料（包内出现未列清单的文件同样拒绝）。
- **签名（可选）**：打包者用 RSA 私钥对清单摘要签名；框架配置公钥后验证签名，构成「内容未变 + 清单可信」的强校验。

**校验模式** `global_var.PACKAGE_INTEGRITY_MODE`：
- `strict`：缺 manifest 或校验失败 → 拒绝安装（强制所有包带清单）
- `warn`（默认）：缺 manifest 仅告警放行（兼容旧包）；有 manifest 则严格校验
- `off`：跳过校验

**签名公钥**：配置 `global_var.PLUGIN_PUBLIC_KEY_PEM`（公钥 PEM 文件路径）后，安装带 `signature` 的包时强制验证签名，失败拒绝；未配置公钥则跳过签名验证（仍做完整性校验）。

**命令行工具** `tools/package.py`（打包/签名/校验一体）：

```bash
# 1. 生成密钥对（仅需签名时）
python tools/package.py genkey -o private.pem --pub public.pem

# 2. 打包（自动生成 manifest.json；--sign 用私钥签名）
python tools/package.py pack ./demo_tool -o demo_tool.zip --type frontend
python tools/package.py pack ./my_plugin -o my_plugin.zip --type backend --sign private.pem --signer "张三"

# 3. 校验（完整性 + 可选签名）
python tools/package.py verify my_plugin.zip --public-key public.pem

# 4. 查看包内容与清单状态
python tools/package.py show my_plugin.zip
```

发布者将公钥分发给框架部署方并配置到 `PLUGIN_PUBLIC_KEY_PEM`；私钥务必妥善保管（泄漏等同可伪造签名）。

---

## 十一、部署说明

### 11.1 环境要求

- Python 3.10+；依赖见 `requirements.txt`（APScheduler 锁定 3.x）。

### 11.2 生产建议

```bash
# 仅本机访问
python app.py

# 局域网访问
FLASKTOOLKIT_HOST=0.0.0.0 FLASKTOOLKIT_PORT=8000 python app.py

# 生产环境务必保持 FLASKTOOLKIT_DEBUG 关闭（默认）
```

### 11.3 日志

日志按级别写入 `logs/`（debug/info/warning/error 分文件），管理页 `get_logs` 仅允许标准级别（白名单）。

---

## 十二、回归测试套件

框架维护回归测试套件（位于项目 `tests/` 目录，项目根路径自动推导，可在任意位置运行，不污染项目文件）：

| 脚本 | 覆盖内容 | 规模 |
|------|---------|------|
| `test_permission.py` | 权限体系（游客/登录/管理员三层 + CSRF） | 20 项 |
| `test_stage2.py` | 安全加固回归 | 19 项 |
| `test_zip_slip.py` | 插件包 zip slip 防路径穿越专项（`..`/绝对路径/盘符拒绝 + 正常落位） | 19 项 |
| `test_pack_meta.py` | 插件包描述一致性（一致/缺失兜底/冲突拒绝/动态 name 不误伤/落盘对齐） | 17 项 |
| `test_reload_race.py` | 热加载重载竞态回归（test client，20 轮重载后会话保持，验证 auth 会话原子写） | 1 项 |
| `test_meta_e2e.py` | 插件包元信息端到端（上传/冲突/已存在/update 刷新/降级拒绝/require 拒绝，隔离目录模式可重复运行） | 10 项 |
| `test_frontend_zip_slip.py` | 前端工具包安全解压 zip slip 专项（`..`/绝对路径/盘符拒绝 + 正常落位 + clean_static 更新清理 + 卸载资源清理） | 21 项 |
| `test_frontend_chain.py` | 前端工具上传/更新/卸载端到端（含页面/静态资源渲染、clean_static、413 上传大小限制） | 23 项 |
| `test_admin_api.py` | 管理端 API 单测（system/info、plugins、stats、logs、factory-reset scope 校验、上传 413/400） | 21 项 |
| `test_factory_reset.py` | Factory Reset 范围测试（部分/全部删除与保留、内置插件保护、空/非法 scope 无副作用） | 37 项 |
| `test_error_pages.py` | 统一错误码页面渲染（404/405 真实触发 + 400/401/403/500 模板，双环境无 auth/带 auth） | 12 项 |
| `test_package_sign.py` | 插件包完整性校验与签名专项（篡改/加料/缺失检测、签名验证、strict/warn/off 模式、路由集成） | 22 项 |
| `test_plugin_cleanup.py` | 插件卸载 installed_files 清单专项（多 .py 包安装清单完整/卸载全清/clean_old 更新清理/越界路径防御） | 23 项 |
| `test_frontend_permission.py` | 前端工具访问控制（三层权限 + 改权限 API 鉴权/边界 + 静态资源一致 + update 保留 permission） | 25 项 |
| `test_tools_ops.py` | 开发运维工具回归（backup 创建/恢复、reset 范围、config 设置/非法值/unset） | 19 项 |
| `test_page_router.py` | 大插件多模板（页面路由 page=True：主入口自动检测、dict/Response 分发、路径参数注入、正斜杠模板名、旧式 page() 兼容） | 17 项 |

```bash
cd FlaskToolkit   # 在项目根目录执行
python tests/test_permission.py       # 20 项（权限体系）
python tests/test_stage2.py           # 19 项（安全加固回归）
python tests/test_zip_slip.py         # 19 项
python tests/test_pack_meta.py        # 17 项
python tests/test_reload_race.py      # 1 项
python tests/test_meta_e2e.py         # 10 项（隔离目录模式）
python tests/test_frontend_zip_slip.py# 21 项
python tests/test_frontend_chain.py   # 23 项（前端工具链路，隔离目录）
python tests/test_admin_api.py        # 21 项（管理端 API，隔离目录）
python tests/test_factory_reset.py    # 37 项（Factory Reset 范围，隔离目录）
python tests/test_error_pages.py      # 12 项（错误码页面，隔离目录）
python tests/test_package_sign.py     # 22 项（完整性校验/签名，隔离目录）
python tests/test_plugin_cleanup.py    # 23 项（插件卸载 installed_files 清单，隔离目录）
python tests/test_frontend_permission.py # 25 项（前端工具访问控制，隔离目录）
python tests/test_tools_ops.py         # 19 项（backup/reset/config 运维工具，隔离目录）
python tests/test_page_router.py       # 17 项（大插件多模板页面路由，隔离目录）
# 合计 16 个脚本 306 项
```

说明：`test_meta_e2e.py` 与 `test_frontend_chain.py` / `test_admin_api.py` / `test_factory_reset.py` / `test_error_pages.py` / `test_package_sign.py` 均通过 mock 基础目录 + `sys.path` 指向临时插件目录运行，不污染真实项目，可重复执行；`test_reload_race.py` 使用 Flask test client，在测试开头手动调用 `load_plugins()` 初始化（`load_plugins` 仅在 `app.py` 的 `main` 段自动调用）。

上传大小限制（413）已由 `test_admin_api.py`（插件包）与 `test_frontend_chain.py`（工具包）覆盖。

---

## 十三、配置管理（tools/config.py）

框架的可配置项（路径、选项、运行参数）可通过命令行工具查看/修改，持久化到 `data/user_config.json`。
**优先级：环境变量 > 用户配置文件 > 默认值**（环境变量仅 HOST/PORT/DEBUG 三项）。

```bash
python tools/config.py show                 # 查看所有可配置项（当前值/来源）
python tools/config.py set <key> <value>    # 设置配置项（自动校验类型）
python tools/config.py unset <key>          # 移除配置项（恢复默认）
python tools/config.py reset                # 清空全部用户配置
python tools/config.py check                # 校验配置合法性
python tools/config.py env                  # 生成环境变量示例
```

主要可配置项：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `HOST` | 127.0.0.1 | 服务绑定地址（FLASKTOOLKIT_HOST 优先） |
| `PORT` | （自动探测） | 服务端口（FLASKTOOLKIT_PORT 优先） |
| `DEBUG` | false | 调试模式（FLASKTOOLKIT_DEBUG 优先） |
| `UPLOAD_TEMP_DIR` | BASE_DIR/temp | 上传临时目录 |
| `FRONTEND_TEMPLATE_DIR` | BASE_DIR/templates/frontend_tools | 前端工具模板/静态资源目录 |
| `FRONTEND_CONFIG_FILE` | BASE_DIR/frontend_tools.json | 前端工具注册配置文件 |
| `PLUGIN_CONFIGS_DIR` | BASE_DIR/plugins/configs | 插件配置目录 |
| `PLUGIN_TEMP_DIR` | BASE_DIR/plugins/temp | 插件临时目录 |
| `PLUGIN_CACHE_DIR` | BASE_DIR/.plugin_cache | 插件扫描缓存目录 |
| `LOG_DIR` | BASE_DIR/logs | 日志目录 |
| `STATS_FILE` | BASE_DIR/data/stats.json | 统计数据文件 |
| `PACKAGE_MAX_UPLOAD_SIZE_MB` | 10 | 插件包/工具包上传大小上限（MB） |
| `PACKAGE_INTEGRITY_MODE` | warn | 完整性校验模式（strict/warn/off） |
| `PLUGIN_PUBLIC_KEY_PEM` | （空） | 插件签名公钥路径 |

示例：

```bash
python tools/config.py set PACKAGE_MAX_UPLOAD_SIZE_MB 20
python tools/config.py set PACKAGE_INTEGRITY_MODE strict
python tools/config.py set HOST 0.0.0.0
python tools/config.py set PORT 8080
python tools/config.py set DEBUG true
```

## 十四、开发运维工具与启动自检

### 14.1 启动完整性自检（core/selfcheck.py）

框架每次启动时执行完整性自检：

- 校验核心文件/目录存在、第三方依赖（flask/flask_cors/apscheduler/watchdog）可导入、数据目录可写；
- 首次启动执行完整自检并在 `data/.initialized` 写入标记，非首次做快速检查；
- 致命问题（核心文件或依赖缺失）中止启动并给出修复提示；可写性问题仅告警。

```bash
python core/selfcheck.py   # 手动执行完整性自检
```

### 14.2 手动备份 / 恢复（tools/backup.py）

在 Factory Reset 前手动备份关键数据，支持重置后还原（建议服务停止时执行）：

```bash
python tools/backup.py create [名称]     # 创建备份（默认时间戳命名）
python tools/backup.py list               # 列出已有备份
python tools/backup.py info <名称>        # 查看某备份内容
python tools/backup.py restore <名称>     # 恢复备份到项目（覆盖式）
```

备份内容：`plugins/configs`、`plugins/status.json`、`plugins/data`、`data`（统计/审计/用户配置）、`frontend_tools.json`、`logs`。

### 14.3 深度重置（tools/reset.py）

在服务停止状态下直接操作文件系统完成重置，可绕过服务运行时文件被占用/锁定的问题（呼应 Factory Reset 的手动备份与运行时限制）：

```bash
python tools/reset.py list                            # 列出可重置范围
python tools/reset.py reset <scope> [scope...]        # 重置指定范围
python tools/reset.py reset all                       # 全部重置
python tools/reset.py reset all --auto-backup         # 先自动备份再全部重置
```

范围与 Factory Reset 一致：`plugins` / `frontend_tools` / `stats_logs` / `sessions` / `temp` / `builtin` / `all`。
