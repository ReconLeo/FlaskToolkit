# Flask插件框架开发规范

> 版本特性与演进史（来龙去脉）见 [Flask-Plugin-Framework-Changelog.md](Flask-Plugin-Framework-Changelog.md)。

## 一、框架特性概览

- **插件化**：后端插件包（`.zip`，含 plugin.json 描述文件 + 主 `.py` + 可选 templates/static）与前端工具（HTML 包）均可动态上传/更新/卸载/启用/禁用。
- **可选鉴权**：`auth` 是可选插件——不安装时系统全员放行；安装后按三层权限控制。
- **三层权限**：游客（public）/ 仅登录（user）/ 仅管理员（admin），由插件通过装饰器自行声明。
- **热重载**：文件监听自动增量重载插件与前端工具，无需重启服务。
- **定时任务**：插件可声明 `scheduled_tasks`，框架自动注册到调度器（Asia/Shanghai 时区）。
- **统计与日志**：API 调用统计、前端工具访问统计自动累积；分级日志落盘。
- **纵深安全（v4.3-4.5）**：AST 静态扫描 → 能力声明交叉校验 → 运行时审计钩子三道防线；插件包完整性校验 + 可选 RSA 签名；登录失败锁定/空闲超时/强制改密；可选 HTTPS。
- **国际化（v4.9）**：JSON 语言包（内置 zh-CN/en，可扩展），模板/后端/前端统一 `t()`，各页面可切换语言 + 翻译工具（v4.15.4）。
- **插件数据配额（v4.9）**：单插件 + 全局总量配额（capabilities `storage:limit` 声明 / `PLUGIN_DATA_LIMIT_MB`），后台空间管理与在线清理。
- **网络可达（v4.11）**：后台网络与访问页（分享链接 + 二维码）、mDNS、IP 变化检测；桌面启动器双击即用（仅本机/局域网一键切换）。
- **安全传输（v4.12）**：自签名 HTTPS + HTTP→HTTPS 308 自动跳转 + Secure Cookie 自动配置，支持反向代理 TLS 终止。
- **统计洞察（v4.14）**：仪表盘运行徽章/冷门插件提示/最近动态、14 天请求趋势、错误 Top、访问画像。
- **Root 权限域与市场铺路（v4.15）**：framework 能力域三档（read/manage/core）、程序化插件管理服务层、插件级更新源。
- **事件总线与真依赖解析（v4.16）**：进程内发布-订阅总线（插件间松耦合通信）、依赖版本约束 + Kahn 拓扑排序。
- **移动端（v4.13/4.17）**：手机/平板/桌面自适应；v4.17 服务端 UA 检测分发独立移动端模板。

---

## 二、项目结构

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
│   ├── plugin_scanner.py      #   插件静态扫描器（AST 后端扫描 + 前端 HTML 扫描，10.6）
│   ├── capabilities.py        #   插件能力声明模型（解析/匹配/交叉校验/运行时授权，10.7）
│   ├── audit_hook.py           #   运行时审计钩子（sys.addaudithook，10.8）
│   ├── selfcheck.py           #   启动完整性自检
│   ├── logging_setup.py       #   日志配置 + 插件日志适配器
│   ├── network.py           #   网络地址中心（局域网 IP / 绑定 / 端口 / 访问地址，v4.11 M1；HTTP→HTTPS 308 跳转 / Secure Cookie 判定，v4.12）
│   ├── mdns.py              #   mDNS 服务注册（可选依赖 zeroconf，v4.11 M2）
│   ├── ip_watcher.py        #   IP 变化检测（快照比较 + 后台线程，v4.11 M4）
│   ├── i18n.py             #   国际化语言包框架（zh-CN + en 内置可扩展，v4.9）
│   ├── quota.py            #   插件数据配额（路径判定 / 用量统计 / enforce / 全局总量，v4.9）
│   ├── update_checker.py   #   版本检查推送（changelog feed + 双后端更新校验，v4.8）
│   ├── framework_manifest.py # 框架目录清单（核心文件/用户数据单一事实来源，v4.15.1）
│   ├── plugin_admin.py     #   程序化插件管理服务层（v4.15，市场铺路）
│   ├── plugin_updates.py   #   插件级更新源（RSA 验签 feed，v4.15）
│   ├── events.py           #   事件总线（进程内发布-订阅，纯 stdlib，v4.16）
│   ├── plugin_deps.py      #   插件依赖解析（semver + Kahn 拓扑 + 环检测，v4.16）
│   ├── device.py           #   设备检测 + 移动端模板分发（UA 分类 / resolve_template，v4.17）

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
├── examples/                  # 官方示例插件/工具包（8 个）+ install_all.py 一键安装
├── tools/                     # 开发运维命令行工具（python tools/xxx.py）
│   ├── config.py              #   配置管理 CLI（show/set/unset/reset/check/env/profile 预设）
│   ├── scan.py                #   插件静态扫描 CLI（.py / .zip / 目录，--json）
│   ├── package.py             #   插件包打包/签名/校验 CLI（genkey/pack/verify/show）
│   ├── backup.py              #   手动备份/恢复工具（Factory Reset 前备份关键数据）
│   ├── gen_cert.py             #   HTTPS 自签名证书生成工具（v4.5.0，openssl）
│   ├── scaffold.py            #   插件脚手架 CLI（backend/frontend 骨架生成，v4.10 M6）
│   ├── install_plugin.py      #   插件离线安装/卸载 CLI（backend/frontend/list/uninstall，v4.10 M6/M6-Extra）
│   ├── desktop_launcher.py  #   桌面启动器（tkinter GUI，subprocess 启动服务，v4.11 M5；HTTPS 复选框 + 证书自动生成，v4.12）

│   └── reset.py               #   深度重置工具（服务停止时使用，绕过运行时文件锁定）
├── tests/                     # 回归测试套件（43 脚本 1143 项 + 端到端链路验证）
├── templates/                 # 页面模板（首页/登录/错误码页 400-500/admin 管理后台/插件页）
│   ├── admin/                 #   管理后台（dashboard / plugins / logs / stats / system）
│   ├── frontend_tools/        #   前端工具模板
│   └── plugins/               #   插件页面模板
├── static/                    # 静态资源（css/main.css 统一设计体系 + error.css 错误页；js/plugin_common.js 统一鉴权前端 + main.js 公共脚本 + index/login/plugin_default/logout 页面脚本）
├── .github/workflows/ci.yml   # GitHub Actions CI 工作流
├── data/                      # 运行时数据（统计/审计/用户配置，已 gitignore）
├── logs/                      # 运行日志（已 gitignore）
├── documents/                 # 开发规范 / Roadmap / CI 上手指南 / 版本收尾 checklist / 版本演进记录
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

桌面启动器（GUI，普通用户免命令行）：`python tools/desktop_launcher.py` —— 启动/停止服务、选择仅本机或局域网共享、一键复制访问地址（v4.11 M5）。

### 3.3 运行环境变量

| 变量                 | 默认值      | 说明                                             |
| -------------------- | ----------- | ------------------------------------------------ |
| `FLASKTOOLKIT_HOST`  | `127.0.0.1` | 绑定地址；默认仅本机访问，局域网访问设 `0.0.0.0` |
| `FLASKTOOLKIT_PORT`  | 自动探测    | 显式指定端口；被占用自动回落探测可用端口         |
| `FLASKTOOLKIT_DEBUG` | 关闭        | 调试模式（`1`/`true`/`yes`/`on` 开启），生产勿开 |

```bash
FLASKTOOLKIT_HOST=0.0.0.0 FLASKTOOLKIT_PORT=8000 python app.py
```

### 3.4 反向代理部署（Nginx TLS 终止，v4.12）

适用场景：**TLS 由 Nginx 等反向代理终止**（框架内部仍为 HTTP），用户通过 `https://` 访问。

> 直连 HTTPS 模式（SSL_CERT_FILE/SSL_KEY_FILE 生效）下，框架自动在**主端口+1** 启动 HTTP→HTTPS 308 跳转端口（保留 POST 方法与 body），访问旧 `http://` 地址自动落到 `https://`；反向代理场景跳转由 Nginx 负责，框架不重复启用。
> `SESSION_COOKIE_SECURE` 默认**自动**（None）：HTTPS 直连或 EXTERNAL_SCHEME=https 时自动开启 Secure，纯 HTTP 局域网自动关闭（防浏览器丢 Cookie），无需手动配置；如需显式强制可用 `set SESSION_COOKIE_SECURE true/false`。

配置（`python tools/config.py set <KEY> <VALUE>`）：

```bash
python tools/config.py set TRUST_PROXY_HEADERS true   # 信任 X-Forwarded-Proto/For/Host（恢复客户端 IP 归因与 request.scheme）
python tools/config.py set EXTERNAL_SCHEME https     # 分享链接/二维码/横幅/桌面启动器显示 https://
python tools/config.py set EXTERNAL_PORT 8443        # 外部端口（Nginx 监听端口；分享地址/二维码用它，0=内部端口）
python tools/config.py set EXTERNAL_HOST your.domain  # 外部域名（可选；不设则自动用本机 IP/主机名，需与证书 SAN 一致）
# python tools/config.py set SESSION_COOKIE_SECURE true  # 可选：显式强制 Cookie Secure（默认已自动）
```

Nginx 配置要点：

```nginx
server {
    listen 443 ssl;
    server_name flasktoolkit.local;           # 与证书 SAN 一致
    ssl_certificate     data/certs/cert.pem;  # 自签名证书（tools/gen_cert.py 生成，SAN 需含实际访问域名/IP）
    ssl_certificate_key data/certs/key.pem;

    client_max_body_size 100m;                # 关键：默认 1MB 会挡住框架 100MB 上传上限

    location / {
        proxy_pass http://127.0.0.1:5010;     # 框架内部 HTTP 端口
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;              # 大文件上传/下载保持连接
        proxy_send_timeout 300s;
    }
}
```

注意事项：

- **仅可信代理后方可开启 `TRUST_PROXY_HEADERS`**——伪造的 X-Forwarded-For 可绕过审计 IP 归因与登录锁定维度（ip_username 防分布式爆破依赖真实客户端 IP）。
- 框架与 Nginx 间为内网 HTTP，`SESSION_COOKIE_SECURE=true` 后浏览器 Cookie 仅经 https 传输，内网明文段不承载 Cookie。
- 框架无 WebSocket/SSE 功能，无需额外长连接配置；子路径挂载（如 `location /ft/`）暂不支持，请使用根路径反代。
- 直连自签名 HTTPS（无代理）时无需上述配置：仅需 `SSL_CERT_FILE` / `SSL_KEY_FILE`（见 3.3），并建议 `SESSION_COOKIE_SECURE=true`。

---

## 四、权限模型（v4.0 核心）

### 4.1 三层权限

| 层级     | 装饰器                  | 说明                              |
| -------- | ----------------------- | --------------------------------- |
| 游客     | `@permission("public")` | 不要求登录（登录/登出、公开信息） |
| 仅登录   | `@permission("user")`   | 需登录（默认兜底）                |
| 仅管理员 | `@permission("admin")`  | 需登录且角色为 admin              |

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

### 4.5.1 插件公开页面（public_page，v4.2.1 新增）

`/plugin/<name>` 页面受全局登录守卫保护（auth 已安装时未登录访问跳转登录页）。若插件希望页面公开（局域网工具、信息落地页、免登录场景），在插件实例上声明 `public_page = True` 即可豁免（由 `routes/interceptor.py` 的 `/plugin/` 守卫识别）；默认 False，不影响其他插件。典型用法：`self.public_page = not self.auth_required`（与插件免登录模式联动，AirDrop 插件即此模式）。

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

| 钩子             | 触发时机                                 | 默认实现                      |
| ---------------- | ---------------------------------------- | ----------------------------- |
| `on_load()`      | 插件加载完成后                           | 空                            |
| `on_ready()`     | 所有插件加载完成后（跨插件依赖最终确认） | 空                            |
| `on_shutdown()`  | 服务停止前                               | 空                            |
| `on_unload()`    | 插件卸载前（显式卸载）                   | 清理本插件订阅的事件（v4.16） |
| `on_uninstall()` | 插件删除前（显式卸载）                   | 空                            |

```python
def on_load(self):
    """初始化资源、连接数据库等"""
    self.logger.info("插件已加载")

def on_ready(self):
    """所有插件加载完成后执行（此时跨插件依赖判断才准确）"""
    self.logger.info("全部插件已就绪")

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

### 5.4.1 事件总线（v4.16）

框架内置轻量进程内事件总线（`core/events.py`，纯 stdlib 观察者模式），用于插件之间、插件与框架之间**松耦合**通信：发布方 `emit` 事件，任意订阅方 `on` 监听，订阅方之间互不知晓、无需依赖声明与方法调用。

BasePlugin 提供事件集成助手，插件无需直接接触 core.events：

```python
from .base_plugin import BasePlugin
from .base_plugin import permission as permission_required

class MyPlugin(BasePlugin):
    name = "my_plugin"

    def on_load(self):
        # 订阅框架内置全局事件（点分命名空间）
        self.on_event('user.login', self._on_user_login)
        self.on_event('plugin.loaded', self._on_plugin_loaded)
        # 订阅自身发布的自定义事件（event_name 自动加 plugin:my_plugin: 前缀）
        self.on_event(self.event_name('heartbeat'), self._on_heartbeat)
        # 异步订阅：async_=True 走后台线程池，不阻塞事件发布
        self.on_event('plugin.loaded', self._on_async, async_=True)

    def _on_user_login(self, event, **data):
        """回调签名 handler(event_name, **data)，异常被框架隔离不影响其他订阅者"""
        self.logger.info(f'用户登录: {data.get("username")}')

    def _on_heartbeat(self, event, **data):
        pass

    def _on_async(self, event, **data):
        pass

    def emit_demo(self):
        # 发布本插件自定义事件（自动加 plugin:my_plugin: 前缀）
        self.emit_event('heartbeat', type='interval', message='运行中')
        # event_name('heartbeat') == 'plugin:my_plugin:heartbeat'，供其他插件订阅
```

**BasePlugin 事件助手**：

| 方法                                                                | 说明                                                                  |
| ------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `on_event(event, handler, *, once=False, async_=False, priority=0)` | 订阅事件；自动 `owner=self` 并登记 `_event_subs`；返回 handler 可链式 |
| `emit_event(name, **data)`                                          | 发布本插件自定义事件，自动加 `plugin:<插件名>:` 前缀                  |
| `event_name(name)`                                                  | 返回 `plugin:<插件名>:<事件名>` 完整名，便于订阅/引用                 |
| `_cleanup_events()`                                                 | 清空本插件订阅的事件（`on_unload` 默认调用，防绑定方法订阅泄漏）      |

内置事件：`plugin.loaded` / `installed` / `uninstalled` / `enabled` / `disabled`、`user.login` / `logout`、`request.finished`。

**示例插件演示**：scheduler_demo（订阅内置 + 自定义事件 + 异步订阅，定时任务 `emit_event` 发布 heartbeat/stats，页面手动发布 manual_trigger）；dependent_demo（跨插件事件订阅——松耦合订阅 scheduler_demo 事件，事件来源归因『跨插件(<name>)』/『框架全局』）。

### 5.4.2 文件传输与异步任务（BasePlugin 能力）

插件通过 BasePlugin 内置能力实现文件上传/下载与耗时任务的异步化，无需自行造轮子。

**上传上限链路**：全局 `MAX_UPLOAD_SIZE_MB`（默认 100MB，`MAX_CONTENT_LENGTH` 兜底）→ 插件级 `max_upload_size`（默认 10MB）→ route 级 `max_upload`，逐级收紧；类型由 `allowed_upload_types` 白名单约束。

| 方法/属性                                     | 说明                                                                                                  |
| --------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `allowed_upload_types`                        | 允许的上传文件扩展名白名单（如 `['.txt', '.csv']`）                                                   |
| `max_upload_size`                             | 插件级上传大小上限（MB，默认 10；可在 route 内用 `max_upload` 覆盖）                                  |
| `check_upload_limit(file, explicit_mb)`       | 上传大小预检（流式 seek/tell，不落盘）；超限返回实际大小（字节），未超限返回 0                        |
| `save_uploaded_file(file_key='file')`         | 保存上传文件（自动做大小预检与类型校验），返回 `(临时路径, 原始文件名)`，超限/类型不符抛 `ValueError` |
| `send_file_response(path, download_name=...)` | 增强文件下载响应（中文名自动 RFC 5987 `filename*` 编码、Range 断点、下载统计计入插件热度）            |
| `run_async_task(fn, *args)`                   | 提交耗时任务到后台线程池，返回 `task_id`，不阻塞请求                                                  |
| `get_async_task_status(task_id)`              | 查询异步任务状态（`running`/`success`/`failed`）                                                      |
| `check_upload(size_bytes)`                    | 上传前存储配额预检（联动 `storage:limit`，见 10.10），超限返回 `{ok: False, remaining_mb: ...}`       |

**异步处理链路**：上传后立即返回 `task_id`，后台线程处理，前端轮询 `get_async_task_status`，完成后 `send_file_response` 下载结果。官方示例 `async_file_demo` 完整演示（上传限制 + 异步任务 + 状态轮询 + 结果下载 + 声明式存储配额）。

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
- 无任何自定义主入口时，插件 API 文档/调试页经 `/__plugin_api__/<name>` 访问（仅管理员，见 8.1）；`/plugin/<name>` 对无自定义主入口的插件返回 404。

**④ 示例**：`hello_plugin` 展示主入口 `page()` + 子页 `about`/`usage`/`greet/<name>`（路径参数）；`multitool_demo` 完整演示大插件三要素（多模板 + 辅助 .py multitool_utils + 静态资源 css/js，含文本分析 API）；`tests/test_page_router.py` 21 项固化页面路由回归（含纯 API 无 name 插件调试页 500 漏洞）。

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

| 字段                        | 必填 | 说明                                                                                                                                                      |
| --------------------------- | ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`                      | 是   | 插件名，须与主 `.py` 文件名一致                                                                                                                           |
| `version`                   | 是   | 版本号（点分数字，支持 `v` 前缀）；update 时须高于当前版本，否则拒绝                                                                                      |
| `title`                     | 否   | 显示名称（覆盖插件类 `title`）                                                                                                                            |
| `author`                    | 否   | 作者（覆盖插件类 `author`）                                                                                                                               |
| `category`                  | 否   | 分类                                                                                                                                                      |
| `description`               | 否   | 描述                                                                                                                                                      |
| `permission`                | 否   | 权限级别（覆盖插件类 `permission`）                                                                                                                       |
| `dependencies`              | 否   | 依赖插件名列表（如 `["auth"]`，v4.16 支持版本约束如 `"auth>=2.0"`，见 5.6.2.1）                                                                           |
| `require_framework_version` | 否   | 最低框架版本要求（点分版本，如 `"4.0.0"`）；非强制，一经声明须满足，见 5.7                                                                                |
| `capabilities`              | 否   | 能力白名单声明（v4.3.2，字符串列表）；未声明的检出行为在 enforce 模式下拒绝安装，见 10.7                                                                  |
| `repo`                      | 否   | 插件源码/发布仓库地址（v4.15，市场铺路元数据；不进描述一致性冲突比对）                                                                                    |
| `update_feed`               | 否   | 插件级更新源 feed URL（v4.15，JSON {latest_version,published_at,download_url,sha256,changes[,signature]}，RSA 验签，应用内 check-updates 触达，见 5.6.8） |

版本以 `plugin.json` 声明为准：上传/更新后描述文件落盘为 `plugins/<name>.json`，插件扫描与目录指纹均优先读取该文件，保证 catalog 显示版本与包内声明一致。

#### 5.6.2.1 依赖声明与版本约束（v4.16）

`dependencies`（依赖插件）与 `pip_dependencies`（第三方 pip 包，v4.10）均支持**名称或带版本约束**的写法：

| 语法                  | 含义                     | 示例             |
| --------------------- | ------------------------ | ---------------- |
| `name`                | 仅要求已安装/已加载      | `"auth"`         |
| `name>=x`             | 版本 ≥ x                 | `"auth>=2.0"`    |
| `name>x`              | 版本 > x                 | `"auth>1.5"`     |
| `name<x` / `name<=x`  | 版本 < x / ≤ x           | `"auth<3"`       |
| `name==x` / `name!=x` | 精确相等 / 不等          | `"auth==2.0.1"`  |
| `name>=a,<b`          | 多约束（逗号，全部满足） | `"auth>=2.0,<3"` |

版本比较为纯 stdlib 简化 semver（数字段 + 预发布权重 a/b/rc），如 `1.0 > 1.0rc1 > 1.0b1 > 1.0a1`。

- **加载**：插件加载器做 Kahn 拓扑排序，先加载依赖；依赖缺失/版本不满足/存在循环时，该插件不加载，`global_var.plugin_load_issues` 记录原因（`dependency_missing` / `dependency_version` / `dependency_circular`），后台插件列表显示『未加载』徽章 + 原因。
- **安装**：安装时校验依赖；卸载时做反向依赖检查（仍被其他插件依赖则阻止卸载）。
- **示例**：`dependent_demo` 声明 `dependencies = ["auth"]`；`scheduler_demo` / `dependent_demo` 通过事件总线松耦合感知彼此（见 5.4.1）。

#### 5.6.3 描述一致性（plugin.json 与插件类属性对齐）

`plugin.json` 与主 `.py` 内的插件类属性是**两份描述**（字段见 5.6.2），上传/更新时框架通过 AST 静态解析主 `.py`（不执行插件代码）做对齐校验：

| 规则          | 说明                                                                                                                                                      |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| name 三处一致 | `plugin.json.name` == 主 `.py` 文件名 == 插件类 `name`（AST 可提取时），任一不一致拒绝上传                                                                |
| 冲突字段拒绝  | `version`/`title`/`author`/`permission`/`category`/`description`/`dependencies`/`require_framework_version` 两处同时声明且不一致 → 拒绝并报告具体冲突字段 |
| 缺失补全      | `plugin.json` 缺失字段回退插件类属性（`version` 缺失用类兜底并告警）                                                                                      |
| 对齐落盘      | 对齐后的完整描述落盘为 `plugins/<name>.json`，为运行时唯一权威                                                                                            |

> **对开发者**：修改插件元信息（版本/标题/权限等）时，需同步更新 `plugin.json` 与插件类属性，否则上传/更新会被拒绝。
>
> 运行时插件扫描以落盘描述文件为权威（缺失字段保留类属性兜底，兼容存量无描述文件插件）；若描述文件 `name` 与类 `name` 不一致则跳过加载并报错。

#### 5.6.4 解压映射

| 包内路径      | 解压目标                            |
| ------------- | ----------------------------------- |
| `<name>.py`   | `plugins/<name>.py`                 |
| `plugin.json` | `plugins/<name>.json`               |
| `templates/*` | `templates/plugins/*`               |
| `static/*`    | `templates/plugins/static/<name>/*` |

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

参考以下插件包源目录结构（`UserManage/`）：

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

#### 5.6.8 插件级更新源与 framework 能力域（v4.15）

**插件级更新源（core/plugin_updates.py）**：插件在 plugin.json 声明 `update_feed`（可选；`repo` 另作市场铺路元数据）后，应用内即可触达其**独立发布渠道**，用于第三方插件市场分发：

| feed 字段        | 必填 | 说明                                                                                  |
| ---------------- | ---- | ------------------------------------------------------------------------------------- |
| `latest_version` | 是   | 最新版本（点分，支持 v 前缀；低于当前不提示更新）                                     |
| `published_at`   | 否   | 发布时间                                                                              |
| `download_url`   | 是   | 新版插件包 .zip 下载地址                                                              |
| `sha256`         | 是   | 包完整性校验（下载后校验）                                                            |
| `changes`        | 否   | 更新说明                                                                              |
| `signature`      | 否   | 签名（配置 `UPDATE_PUBLIC_KEY_PEM` 后强制 RSA 验签，`package_sign.verify_signature`） |

- **缓存**：`data/cache/plugin_updates.json`（`UPDATE_CHECK_INTERVAL` 小时，默认 24）。
- **静默失败**：网络 3s 超时 / 校验失败不阻断，仅标记该插件不可更新。
- **入口**：后台插件页"检查更新"按钮 / catalog 更新徽章（⬆ vX 可更新）。

**framework 能力域（core/capabilities.py）**：插件声明 `framework:read` / `framework:manage` / `framework:core` 可操作**框架自身核心文件**（core/routes/templates 框架部分/app.py/global_var.py/data/user_config.json/plugins/status.json，豁免 templates/plugins/、templates/frontend_tools/、plugins/data|temp|configs）。`core` 为最高档（隐含 manage/read，≈Linux **root**，可修改/删除核心文件）。运行时由 `check_framework(plugin_name, level)` 判定；`filesystem:write` 命中核心路径会被拒绝并要求改用 `framework:core`；放行的核心路径写自动落 **root-access 审计事件**。⚠️ **MIT 协议下框架概不负责**，仅应在充分信任的可信插件上使用。

### 5.7 最低框架版本要求（require_framework_version）

后端插件可声明 `require_framework_version`（`plugin.json` 或插件类属性，非强制），用于声明插件所需的最低框架版本，以支撑框架持续迭代：

- **未声明**：不检查，任意框架版本可用。
- **声明了**：上传/更新时与 `global_var.FRAMEWORK_VERSION`（当前 `4.17.0`）做点分版本比较（`compare_versions`，修复了前端工具原先字符串比较的缺陷）；插件要求高于框架版本 → 拒绝安装并报告。
- **运行时双重校验**：`load_plugins` 加载时同样校验（防止手工放置插件绕过上传校验），不满足则跳过加载并报错。
- 参与描述一致性对齐（冲突拒绝/缺失补全），见 5.6.3。

```json
// plugin.json 示例：要求框架 ≥ 4.0.0
{"name": "user_manage", "version": "1.0.1", "require_framework_version": "4.0.0"}
```

### 5.8 内置插件（Builtin）

框架内置随系统分发、不可卸载的插件（`global_var.BUILTIN_PLUGINS`）：

| 插件          | 说明                                                             |
| ------------- | ---------------------------------------------------------------- |
| `auth`        | 认证/会话/权限（可选插件，但作为内置分发；未安装时游客模式放行） |
| `user_manage` | 用户管理（作为内置插件，同时充当插件包机制的官方演示）           |

- **受保护**：管理页插件列表展示内置徽标；卸载接口拒绝删除内置插件；Factory Reset 的 `plugins` 范围跳过内置插件。
- **随框架分发**：内置插件的 `.py`、描述文件、模板与静态资源随项目存放，加载方式与其他插件一致。
- **默认账号**：`auth` 在无用户配置时自动重建默认管理员 `admin/admin123`（可被 Factory Reset 的 `builtin` 范围重置）。
- **权限模型不变**：内置插件同样通过装饰器声明三层权限（游客/登录/管理员）。

### 5.9 Factory Reset（重置）

将部分/全部框架数据还原至安装初始状态。接口 `POST /api/admin/factory-reset`（管理员权限，body 带 `X-CSRF-Token`），请求体 `scope`：

| 值                 | 重置内容                                                                           |
| ------------------ | ---------------------------------------------------------------------------------- |
| `"all"`            | 全部（下列所有范围 + 内置配置）                                                    |
| `"plugins"`        | 清除全部非内置插件（.py / 描述文件 / 模板 / 静态资源 / 临时目录），内置插件受保护  |
| `"frontend_tools"` | 清除前端工具（清单 + 模板目录）                                                    |
| `"stats_logs"`     | 清除调用统计 `data/stats.json`（含内存统计）与日志 `logs/`                         |
| `"sessions"`       | 清除登录会话 `plugins/data/sessions.json`                                          |
| `"temp"`           | 清除运行产生的临时文件（`.plugin_cache`、`__pycache__`、`temp/`、`plugins/temp/`） |

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

### 5.10 移动端/桌面端页面分离（v4.17）

**目标**：移动端页面脱离 v4.13『桌面端 + `xxx_mobile.css`/`mobile.js` 样式补充』模式，改为**同 URL + 服务端 UA 检测分发独立模板**——手机端渲染精简独立模板，平板/桌面走桌面端响应式模板避免退化。纯 stdlib，无新增运行时依赖。

#### 5.10.1 设备检测 core/device.py

| 函数                        | 说明                                                                                                             |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `detect_device(user_agent)` | 按 UA 返回 `mobile`/`tablet`/`desktop`（复用 `core/stats.classify_device`；bot/爬虫视为 desktop 不强制移动端）   |
| `get_device()`              | 当前请求设备类型（读 UA）；`FORCE_MOBILE=True` 时强制返回 mobile                                                 |
| `is_mobile()`               | 当前请求是否手机端（仅 mobile 为 True；tablet 走桌面响应式；`MOBILE_ENABLED=False` 全回退；`FORCE_MOBILE` 强制） |
| `mobile_enabled()`          | 移动端分离开关（读 `MOBILE_ENABLED`）                                                                            |
| `resolve_template(name)`    | 手机端且存在 `templates/mobile/<name>` → 返回移动端模板；否则回退桌面端模板（安全回退避免 500）                  |
| `render(template, **ctx)`   | 统一渲染入口：`render_template(resolve_template(template))`                                                      |

配置项（`global_var.py` + CONFIG_ITEMS）：

- `MOBILE_ENABLED=True`：移动端页面分离开关（关则全部回退桌面端模板）。
- `FORCE_MOBILE=False`：调试/测试强制手机端（`is_mobile()` 恒 True）。

`app.py` 通过 `inject_device` context_processor 向模板注入 `is_mobile`/`device`/`mobile_enabled`。

#### 5.10.2 移动端模板命名空间与分发

- **框架公开页**：`templates/mobile/<name>`（如 `mobile/login.html`、`mobile/index.html`），配合 `static/css/mobile-app.css` 精简移动端布局层。渲染点改用 `device.render`（`routes/public.py` 登录页/首页）。
- **后台**：`templates/mobile/admin/<template>` 开放独立能力（`_admin_page` 已用 `device.render`）；后台沿用响应式 base 保底。
- **插件页**：移动端命名空间 `templates/plugins/<name>/mobile/<template>`。BasePlugin 已增强：`_resolve_template(template, mobile=True)` 优先查找该命名空间，`is_mobile_context()`/`mobile_template()` 辅助，`render()`/`render_plugin_page()` 移动端自动分发，`routes/plugin.py` 子页面分发接入。**插件接入移动端独立渲染只需放同名模板，无需改视图**。

#### 5.10.3 插件接入移动端独立渲染

1. 在 `templates/plugins/<name>/mobile/` 放置与桌面端同名的模板（主入口 + 各 page=True 子页）。
2. 移动端模板复用框架 `static/css/mobile-app.css`（或自带精简样式），触屏友好（≥44px 目标、单列卡片、大按钮）。
3. 保持 JS 所需 DOM id（如 corp_tools 的 `#corp-health` 等），前端逻辑复用。
4. `require_framework_version` 声明 `4.17.0`（使用移动端能力）。
5. 平板/桌面仍渲染桌面端模板；不提供移动端模板的插件自动回退桌面端模板（兼容）。

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
- **已知问题（v4.2.1 已修复）**：`request()` 曾与全局 XHR `send` 拦截**双重注入 `X-CSRF-Token`**，同名头被浏览器逗号拼接为 `token, token`，鉴权模式下写请求后端 CSRF 双提交校验返回 403。现已移除 `request()` 内手动注入（全局拦截统一注入一次）。使用原生 `fetch` / `XMLHttpRequest` 的页面不受影响（全局拦截单次注入）。

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

| 值               | 含义                                                       |
| ---------------- | ---------------------------------------------------------- |
| `public`（默认） | 游客可直接访问                                             |
| `user`           | 需登录；未登录访问页面/静态资源跳转登录页（携带 redirect） |
| `admin`          | 仅管理员；普通用户访问返回 403 页，未登录跳转登录页        |

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

| HTTP / code | 含义                              | API 返回示例                                              | 页面表现       |
| ----------- | --------------------------------- | --------------------------------------------------------- | -------------- |
| `200`       | 成功                              | `{"code": 200, "message": "操作成功", "data": ...}`       | 正常渲染       |
| `400`       | 参数错误 / 校验失败               | `{"code": 400, "message": "缺少 username", "data": null}` | 400 错误页     |
| `401`       | 未登录 / 会话过期                 | `{"code": 401, "message": "未登录或登录已过期"}`          | 页面跳转登录页 |
| `403`       | 权限不足 / CSRF 失败              | `{"code": 403, "message": "需要管理员权限"}`              | 403 错误页     |
| `404`       | 资源不存在（插件未加载/路径错误） | `{"code": 404, "message": "API路径 /xxx 不存在"}`         | 404 错误页     |
| `405`       | 请求方法不支持                    | `{"code": 405, "message": "不支持的请求方法 ..."}`        | 405 错误页     |
| `500`       | 服务器内部错误                    | `{"code": 500, "message": "接口调用失败: ..."}`           | 500 错误页     |

- API 错误响应统一走 `error_response(message, code)`，HTTP 状态码与 body.code 一致。
- 页面错误统一使用 `templates/*.html`（400/401/403/404/405/500），共享 `static/css/error.css` 统一设计风格。
- 401 在页面场景下自动携带 `redirect` 参数跳转登录页；403 可跳转 `/403?message=...` 展示具体原因。

---

## 八、路由规则与路径规范

- 插件 API 统一走 `/api/<plugin_name>/<path>` 分发（由框架 `routes/plugin.py` 处理）。
- 插件页面统一走 `/plugin/<plugin_name>`。
- 管理端接口（`/api/admin/*`）框架已默认强制管理员权限，插件无需也不应声明。
- 未加载/已禁用的插件访问返回 404（非 500）。

### 8.1 公共页面（首页 / 登录 / 登出 / 插件 API 文档页）

公共页面共享 `static/css/main.css` 统一设计体系（以首页风格为准：深色导航栏、主色蓝 `#3498db`、成功绿 `#27ae60`、卡片圆角）与 `static/js/main.js` 公共脚本（`FT.getCookie` / `FT.checkAuth` / `FT.doLogout`）：

| 页面                 | 路径                              | 功能                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| -------------------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 首页                 | `/`                               | 工具卡片按分类展示；工具条支持**搜索**（名称/描述/作者/分类实时过滤）与**排序**（默认/热度/字母，分类内排序）；热度=后端插件 API 调用总数、前端工具访问数（渲染时注入 `data-heat`）                                                                                                                                                                                                                                                                                                  |
| 登录                 | `/login`                          | 记住用户名（localStorage）、显示/隐藏密码、回车提交、防重复提交、登录成功页 + redirect 安全回跳（拒绝站外与 `/login` 自身）；**429 登录锁定冷却（v4.3.0）**：展示后端通用信息并禁用登录按钮 30s（前端固定冷却，不泄露后端实际锁定剩余时间）                                                                                                                                                                                                                                          |
| 登出                 | `/logout`                         | 调用登出接口清理 Cookie + 成功页（自动/手动跳转登录）                                                                                                                                                                                                                                                                                                                                                                                                                                |
| 插件 API 文档/调试页 | `/__plugin_api__/<name>`（v4.10） | **任何插件（含非裸插件）均可直达**；列出插件全部 API 与参数（string/boolean/file/array/object **+ 路径参数 `<name>`/`<int:name>` 输入框**），可视化调用并展示 JSON 结果（**HTTP 状态码/耗时/业务 code/实际请求 URL**）；**非安全方法自动携带 CSRF**；**PUT/DELETE 与 POST 一致发 JSON body**；一键复制/折叠结果、请求历史；**仅管理员可见**（`ADMIN_GUARD_PREFIXES` 守卫：游客 302 / 普通用户 403 / 管理员 200）；后台插件管理页"API 文档"按钮可直达；属插件测试工具，功能改动需谨慎 |

> **/plugin/ 页面登录守卫**：auth 插件已安装时，`/plugin/` 下所有页面默认需登录（全局 `before_request` 守卫，未登录跳转登录页携带 redirect）。插件声明 `public_page=True` 可豁免（见 4.5.1）；`/static/` 静态资源始终公开。

### 8.2 管理后台页面

管理后台提供前端页面管理 FlaskToolkit 应用（入口 `/admin/dashboard`，首页右上角「🛠️ 管理后台」按钮），统一继承 `templates/admin/base.html` 布局（顶部导航：仪表盘/插件管理/日志/统计/系统管理/网络与访问 + 用户信息 + 退出登录），**所有页面路由加 `@admin_api` 保护**（未登录 302 跳登录页携带 redirect、普通用户渲染 403 页、auth 未安装时放行）：

| 页面       | 路径               | 功能                                                                                                                                                                                      |
| ---------- | ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 仪表盘     | `/admin/dashboard` | 统计卡片 + 运行徽章行（运行时长/协议/访问地址数/IP 变化）+ 冷门插件提示 + 最近动态卡 + 系统信息 + 快捷入口 + 内置插件列表（v4.14）                                                        |
| 插件管理   | `/admin/plugins`   | 上传（能力预览两段式，v4.10）/ 更新 / 卸载 / 启用 / 禁用 / 配置 / 全部重置；更新徽章（⬆ 可更新）与 ⚠️ Root 徽章（v4.15）；插件空间卡片 + 在线清理（v4.9.2/4.10）；"API 文档"按钮直达调试页 |
| 日志       | `/admin/logs`      | 按级别与行数查看日志、按插件过滤                                                                                                                                                          |
| 统计       | `/admin/stats`     | API 调用 Top100（可搜索）+ 前端访问 Top100 + 14 天请求趋势（纯 SVG）+ 错误 Top + 访问画像（按登录用户/按游客 IP，含设备分类）+ 审计违规统计卡（v4.14）                                    |
| 系统管理   | `/admin/system`    | 系统信息 + 插件空间管理（配额/用量/在线清理）+ Factory Reset 分 scope 勾选 / 全部重置（见 5.9）                                                                                           |
| 网络与访问 | `/admin/network`   | 分享链接 + 二维码、共享开关（HOST）、mDNS 开关与主机名、IP 变化检测间隔、当前网络状态与防火墙提示（v4.11）                                                                                |

### 8.3 管理端接口

- `GET /api/admin/system/info`：框架版本、内置插件列表、Python/平台版本、base_dir、host、debug 标志与各类统计数（仪表盘与系统页数据源）。
- `GET /api/admin/stats`：插件数（含 catalog）、前端工具数、API 调用与前端访问统计明细。
- `GET /api/admin/logs`：按 `level`/`lines`/`plugin` 读取日志；级别白名单（非法值回退 info），级别映射到 `app.log`（INFO+）与 `error.log`（ERROR+），warning/critical 按行内 ` - LEVEL - ` 标记二次过滤。

---

## 十、插件信任模型与安全

### 10.1 信任模型（重要）

**插件即代码**：后端插件（`plugins/*.py`）与前端工具（HTML/JS/CSS）被框架**直接加载执行**，运行在 Flask 服务进程内，拥有与框架等同的文件系统与网络权限，**无沙箱隔离**。

因此：

- **安装插件即信任其作者**。只应安装来源可信、经过审查的插件包。
- 管理后台「插件管理」页安装/更新/启用插件前，请确认插件包来源与内容；v4.10 起上传接口为「能力预览 + 确认」两段式（依赖 / pip 依赖 / capabilities 声明 / 静态扫描摘要先展示，确认后才落盘安装）。
- 框架不对插件行为做运行时隔离；插件导致的任何数据/安全影响由安装者自行承担。

**裸信任之上叠加纵深防御**：框架在"安装=信任"的底线之上分层提供缓解手段——不改变底线，只提高防线强度：

| 阶段      | 防线                                                       | 章节        |
| --------- | ---------------------------------------------------------- | ----------- |
| 安装期    | 插件包完整性校验 + 可选 RSA 签名（manifest sha256 清单）   | 10.5        |
| 安装期    | AST 静态扫描（危险导入/调用/混淆/范围提取）                | 10.6        |
| 安装期    | capabilities 能力声明与交叉校验（Deny by Default）         | 10.7        |
| 运行时    | 审计钩子（sys.addaudithook 实时拦截，off/observe/enforce） | 10.8        |
| 运行时    | 插件数据配额（单插件 + 全局总量，防写盘失控）              | 10.10/10.11 |
| 传输/访问 | 可选鉴权（三层权限 + 登录锁定 + 空闲超时 + 强制改密）      | 4 / 10.2    |
| 传输/访问 | HTTPS 直连 + HTTP→HTTPS 308 自动跳转 + Secure Cookie 自动  | 10.2/10.9   |

**适用边界**：该信任模型针对**可信局域网 / 企业内网**的日常工具场景（配合 `auth` 插件，可选 `PLUGIN_SCAN_MODE=enforce` + `AUDIT_HOOK_MODE=enforce` + HTTPS）。暴露到对抗性公网仍需自行风险评估——插件始终无沙箱。

### 10.2 系统安全配置（v4.3.0）

框架提供系统级安全开关（`global_var` 配置项，经 `tools/config.py` 调整，见 8.1）：

| 配置项                  | 默认值         | 说明                                                                                                                                                                             |
| ----------------------- | -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SECURITY_HEADERS`      | `True`         | 统一注入安全响应头（X-Content-Type-Options / X-Frame-Options / CSP / Referrer-Policy / Permissions-Policy）并移除 Server / X-Powered-By 指纹头                                   |
| `SESSION_COOKIE_SECURE` | `None`（自动） | 会话/CSRF Cookie 加 Secure 属性（v4.12 默认自动：HTTPS 直连或反代 `EXTERNAL_SCHEME=https` 时自动 True，纯 HTTP 局域网自动 False 防浏览器丢弃 Cookie；`true`/`false` 可显式强制） |
| `TRUST_PROXY_HEADERS`   | `False`        | 反向代理头信任（v4.12，TLS 在 Nginx 等代理终止时开启；信任 X-Forwarded-Proto/For/Host，恢复客户端 IP 归因；**仅可信代理后方可开启**）                                            |
| `LOGIN_MAX_ATTEMPTS`    | `5`            | 登录连续失败锁定阈值（次）                                                                                                                                                       |
| `LOGIN_LOCK_SECONDS`    | `900`          | 登录失败锁定时长（秒，默认 15 分钟）                                                                                                                                             |
| `LOGIN_LOCK_MODE`       | `ip_username`  | 登录锁定维度：`username`=仅用户名 / `ip_username`=IP+用户名（默认，防分布式爆破）/ `off`=禁用锁定（不安全，仅信任局域网时使用）                                                  |
| `SESSION_IDLE_TIMEOUT`  | `1800`         | 会话空闲超时（秒，默认 30 分钟；超过未活动即失效）                                                                                                                               |
| `PLUGIN_SCAN_MODE`      | `report`       | 插件安装校验门禁（v4.3.1 静态扫描 + v4.3.2 capabilities 交叉校验）：`off` 跳过 / `report` 放行附摘要（默认） / `enforce` 高风险或未声明行为拒绝安装，详见 10.6 / 10.7            |
| `AUDIT_HOOK_MODE`       | `observe`      | 运行时审计钩子（v4.4.0）：`off` 不安装 / `observe` 记录不阻断（默认） / `enforce` 未授权行为阻断（网络白名单即防火墙），详见 10.8                                                |
| `SSL_CERT_FILE`         | ``             | HTTPS 证书 PEM 文件路径（v4.5.0，`kind=path`）；与 `SSL_KEY_FILE` 均配置且存在时启用 HTTPS，默认空=HTTP，生成自签名证书见 `tools/gen_cert.py`（10.9）                            |
| `SSL_KEY_FILE`          | ``             | HTTPS 私钥 PEM 文件路径；与 `SSL_CERT_FILE` 配对，仅配一项时回退 HTTP 并告警                                                                                                     |

**登录失败锁定行为**：锁定期间登录接口统一返回 HTTP 429 与通用错误信息（不泄露锁定剩余时间等细节）；登录成功后自动清除对应维度的失败计数；锁定计数仅存内存（重启即清零）。

**手动解封（v4.5.1）**：管理员可在 user_manage 用户管理页查看各用户锁定状态（列表 `locked` 字段）并**一键解封**（`POST /api/user_manage/unlock`，admin 权限）——清除该用户名全部维度（username / ip_username）锁定记录，无需等待锁定期满即可立即登录；解封不存在用户返回 404，解封未锁定用户幂等返回提示。

**HTTPS 自动跳转与 Secure 自动配置（v4.12）**：直连 HTTPS 模式（`SSL_CERT_FILE`/`SSL_KEY_FILE` 均生效）下，框架自动在**主端口+1** 启动 HTTP 跳转端口，所有请求以 **308**（保留 POST 方法与 body）跳转到 `https://<主端口><原路径>`（反向代理场景不启用，跳转由 Nginx 负责，见 3.4）；`SESSION_COOKIE_SECURE` 按 3.4 的自动判定接入 auth 两处 set_cookie（token / csrf_token），无需手动配置。

### 10.3 上传大小限制

- 管理后台上传的**后端插件包**与**前端工具包**统一受 `global_var.PACKAGE_MAX_UPLOAD_SIZE`（默认 10MB）限制，超限返回 `413 Payload Too Large`。
- **全局文件上传上限**：`global_var.MAX_UPLOAD_SIZE_MB`（默认 100MB，映射 `MAX_UPLOAD_SIZE`，`MAX_CONTENT_LENGTH` 兜底）约束插件数据上传的请求体总大小；插件自身的数据上传接口由插件通过 `BasePlugin.max_upload_size`（默认 10MB）与 route 级 `max_upload` 在此内逐级收紧（见 5.4.2）。

### 10.4 Factory Reset（恢复出厂设置）

**设计意图**：将部分/全部框架数据还原至安装初始状态，**不提供自动备份**（恢复初始状态即意图，数据丢失由用户自行承担）——执行前务必先用 `tools/backup.py` 手动备份（见 14.2）。

**范围**（管理后台系统页重置弹窗 / `core/factory_reset.py`，`all` = 下列全部 + `builtin`）：

| 范围             | 语义                                                                                                                                                      |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `plugins`        | 清除全部非内置插件（.py / 描述文件 / 模板 / 静态 / temp 子目录 / **插件数据目录** `plugins/data/<name>/`——v4.10 M6-Extra 补漏，与单插件空间清理语义一致） |
| `frontend_tools` | 移除全部前端工具注册与文件                                                                                                                                |
| `stats_logs`     | 清空统计与日志                                                                                                                                            |
| `sessions`       | 清空会话                                                                                                                                                  |
| `temp`           | 清空临时目录                                                                                                                                              |
| `builtin`        | 还原内置插件配置（`all` 范围自动附带）                                                                                                                    |

- **内置插件保护**：`auth`、`user_manage` 在重置中受保护不被删除；`builtin`/`all` 范围重置其配置（auth 恢复默认 `admin/admin123`，v4.10 起首次登录强制改密向导仍生效）。
- **不可逆确认**：管理后台重置弹窗内置「不可撤销、请先备份」风险提示，确认后才执行；重置过程记录 `cleaned`/`failed` 清单并写审计日志。
- **运行时限制**：服务运行期间文件被占用时重置可能失败——**深度重置 CLI**（`tools/reset.py`，见 14.3）在服务停止状态下直接操作文件系统完成同样范围的重置，支持 `--auto-backup` 先备份再重置。

### 10.5 插件包完整性校验与签名（方案C）

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

### 10.6 插件静态扫描（v4.3.1，P1 阶段一）

管理后台安装/更新插件包与前端工具包时，框架先经 **AST 静态扫描器**（`core/plugin_scanner.py`）检查代码行为，再决定放行或拒绝——在"安装插件即信任其作者"的前提下，为安装者提供一道自动化内容审查。

**后端扫描能力（AST 级）**：

- 危险导入：high——`subprocess` / `ctypes` / `pickle` / `marshal` / `dill` 等；medium——`socket` / `ssl` / `requests` / `httpx` / `urllib.request` / `importlib` 等
- 危险调用：high——`os.system` / `subprocess.Popen` / `eval` / `exec` / `compile` / `__import__` / `shutil.rmtree` / `pickle.loads` 等；medium——`os.remove` / `os.chmod` / `requests.*` / `socket.socket` 等
- socket 服务端（`bind` / `listen`）视为 high；`import as` 别名与实例别名（`s = socket.socket()` 后 `s.connect(...)`）均可归因
- 混淆检测：`eval`/`exec` 参数含 `base64.b64decode` / `zlib.decompress` 等 → obfuscation high；`__import__` 参数非常量 → 混淆告警
- 语法错误（可能是人为规避解析）→ high
- **范围提取**：`paths_read` / `paths_written`（`open` 路径字面量按读写模式分类）/ `network_endpoints`（requests URL、`socket.connect` 主机、字符串常量中的 URL 兜底）——P1 阶段二 capabilities 声明交叉校验的基准
- 插件包（.zip）扫描跳过 `__pycache__` / `templates/` / `static/` 中的模板静态内容

**前端扫描（HTML，正则级）**：`eval` / `new Function`（high）、外部 `<script src>` 与 fetch/XHR 外链（medium）、`document.cookie` / `localStorage`（low），并提取外链端点。

**门禁模式 `PLUGIN_SCAN_MODE`**：

| 模式             | 行为                                                                                  |
| ---------------- | ------------------------------------------------------------------------------------- |
| `off`            | 跳过扫描                                                                              |
| `report`（默认） | 放行安装，响应附 `scan` 摘要与 `scan_scope` 范围，审计日志记录                        |
| `enforce`        | 检出高风险（high > 0）即拒绝安装，返回 400 附完整 `scan_report`，审计日志记录 blocked |

接入端点：后端插件上传/更新（`routes/admin.py`）与前端工具上传/更新（`routes/frontend.py`）共四处。

**扫描 CLI（`tools/scan.py`）**——发布者分发前自检：

```bash
python tools/scan.py my_plugin.py         # 单文件
python tools/scan.py my_plugin.zip        # 插件包 / 前端工具包（config.json 自动识别）
python tools/scan.py plugins/             # 目录批量（递归 .py）
python tools/scan.py my_plugin.zip --json # 机器可读输出
# 退出码：0 无高风险 / 1 检出高风险 / 2 错误
```

**安全配置预设（`tools/config.py profile`）**：将分散的安全开关收拢为三套官方预设，一键套用后仍可 `set` 单项微调：

| 预设       | 定位                 | 关键差异                                                                                 |
| ---------- | -------------------- | ---------------------------------------------------------------------------------------- |
| `daily`    | 日常使用（默认基线） | 扫描 report、完整性 warn、锁定 ip_username 5 次/15 分钟、Cookie Secure 关                |
| `strict`   | 运维加固（需 HTTPS） | 扫描 enforce、完整性 strict、依赖严格、锁定 3 次/30 分钟、空闲 15 分钟、Cookie Secure 开 |
| `lan-open` | 可信局域网开放       | 扫描 off、登录锁定 off（仅在内网用户与插件来源完全可信时使用）                           |

```bash
python tools/config.py profile daily    # 套用预设（返回变更清单）
python tools/config.py set PLUGIN_SCAN_MODE enforce   # 单项覆盖
```

---

### 10.7 插件能力声明（capabilities，v4.3.2，P1 阶段二）

插件在 plugin.json 中以可选字段 `capabilities` 声明**白名单授权**（扁平字符串列表，语法 `域:子域:参数`），安装时与静态扫描的行为范围（10.6）交叉校验。核心哲学：**Deny by Default，声明即授权**——扫描器输出的是"事实"，capabilities 是"授权"，两者比对产生 mismatch 清单。

**能力目录（10 大域，开放集合）**：

| 域         | 能力项            | 语法                                                                                 | 授权语义                                                                                                                                                                                                               |
| ---------- | ----------------- | ------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| filesystem | 读 / 写           | `filesystem:read:<path>` / `filesystem:write:<path>`                                 | 路径前缀授权（目录级含子内容；`data`、`data/`、`data/*` 三写法等价；支持绝对路径与 UNC）                                                                                                                               |
| network    | HTTP 出站         | `network:http:<scheme://host[:port][/path*]>`                                        | host 精确或 `*.dom` 子域通配（**禁裸 `*`**）；声明带端口须精确，不带=任意；path 前缀                                                                                                                                   |
|            | TCP/UDP           | `network:tcp:<host[:port]>` / `network:udp:...`                                      | host 精确；无端口=任意端口                                                                                                                                                                                             |
|            | 监听服务          | `network:server:<host:port>`                                                         | 插件 bind/listen 监听端口                                                                                                                                                                                              |
| webhook    | 群机器人          | `webhook:<platform>:<url-pattern>`                                                   | 平台枚举 wecom/dingtalk/feishu；URL 语义同 network:http（兼作 HTTP 出站授权）                                                                                                                                          |
| process    | 子进程            | `process:exec` / `process:exec:<bin>`                                                | 无参=任意子进程（高危）；带 bin=仅该可执行名（运行时比对）                                                                                                                                                             |
| scheduler  | 定时任务          | `scheduler`                                                                          | 允许注册 APScheduler 任务                                                                                                                                                                                              |
| database   | 数据库            | `database:sqlite:<path>` / `database:mysql:<host:port/db>` / `database:postgres:...` | 连接目标                                                                                                                                                                                                               |
| device     | 串口/打印         | `device:serial:<port>` / `device:print`                                              | 串口枚举（如 COM3）                                                                                                                                                                                                    |
| framework  | 框架核心（v4.15） | `framework:read` / `framework:manage` / `framework:core`                             | 操作框架自身核心文件的三档授权：read=读取 / manage=插件管理与框架配置修改（服务层 require_manage）/ **core ≈ Linux root**（隐含 manage+read，可修改/删除框架核心文件，高危，MIT 协议框架概不负责）；无参数，按级别判定 |
| env        | 环境变量          | `env:read:<pattern>`                                                                 | 变量名前缀或 `*` 通配                                                                                                                                                                                                  |
| storage    | 存储配额          | `storage:limit:<size>`                                                               | 存储空间授权（v4.9.1）：插件声明配额覆盖全局默认；纯数字=MB 或带单位 mb/m/gb/g（须 > 0）                                                                                                                               |

声明示例：

```json
{
  "name": "hr_report",
  "version": "1.0.2",
  "capabilities": [
    "filesystem:read:D:/shared/reports",
    "filesystem:write:plugins/data/hr_report",
    "network:http:https://erp.corp.local/*",
    "webhook:wecom:https://qyapi.weixin.qq.com/cgi-bin/*",
    "database:mysql:10.0.0.5:3306/hr",
    "scheduler",
    "process:exec:ffmpeg",
    "env:read:LDAP_*"
  ]
}
```

**自属路径隐式豁免（implicit grants）**：插件自己的以下路径**无需声明**即可读写——

| 路径                          | 说明                                                         |
| ----------------------------- | ------------------------------------------------------------ |
| `plugins/configs/<name>.json` | 基类 `load_config()` / `save_config()`                       |
| `plugins/data/<name>/**`      | 插件专属数据目录（`self.data_dir` / `self.get_data_path()`） |
| `plugins/temp/<name>/**`      | 插件专属临时目录                                             |

跨插件目录（如插件 A 写 `plugins/data/B/`）与 `data/`（框架自身数据）**不在豁免范围**，仍须显式声明。基类 `get_data_path()` 拼接写法扫描器提取不到路径字面量，该盲区由运行时审计钩子（4.4.0）以 `check_filesystem()` 兜底。

**交叉校验与门禁**（并入 `PLUGIN_SCAN_MODE`，与静态扫描共用三档）：

| 模式             | 行为                                                                                       |
| ---------------- | ------------------------------------------------------------------------------------------ |
| `off`            | 跳过扫描与能力校验                                                                         |
| `report`（默认） | 放行，响应附 `capabilities`（`declared` 已声明 / `missing` 未声明 / `suggested` 建议声明） |
| `enforce`        | 高风险（high > 0）**或** `missing` 非空 → 400 拒绝，附完整缺失清单与建议声明               |

**建议声明自动生成**：`suggested` 字段按检出行为归一化生成（文件路径→父目录、URL→主机根、端口/子进程→对应能力项），可整段复制回 plugin.json，降低声明编写门槛；声明了但未检出使用的能力仅 `unused` 提示（info 级，不阻断），鼓励最小授权。

**运行时授权基准**：插件加载时 loader 从描述文件读取 capabilities 注册进 `core/capabilities.py` 内存注册表；`check_filesystem(plugin, path, mode)` / `check_network(plugin, endpoint)` / `check_process(plugin, bin)` 为 4.4.0 运行时审计钩子的授权判定契约——`check_network` 的 host 匹配即网络白名单"防火墙"规则。未注册/未声明一律拒绝（fail-closed）。

**向后兼容**：旧插件无 `capabilities` 字段——report 模式放行附告警；enforce 模式下若有未声明检出行为则拒绝（良性插件扫描范围通常为空，不受影响）。plugin.json 在 manifest.json 完整性清单内，装后私改 capabilities 会被完整性校验拦截。

> **官方示例维护约定**：`examples/` 下的示例插件须与最新开发规范保持同步——`require_framework_version` 需高于所用框架 API 的引入版本（如使用 `get_data_path` 的示例要求 ≥ 4.3.2）；示例内容变更时同步升级 `version`（plugin.json 与插件类属性两处一致，见 5.6.3），保证 `update` 可重复安装。综合示例 `corp_tools`（企业内网工具箱）演示 capabilities 网络白名单与权限过滤导航，设计见 `documents/archive/Plugin-Design-corp_tools.md`。

---

### 10.8 运行时审计钩子（v4.4.0，P1 阶段三）

基于 CPython 原生 `sys.addaudithook` 的运行时防线（`core/audit_hook.py`）：插件**执行期间**的敏感操作被实时拦截并判定，与安装期两条防线（10.6 静态扫描、10.7 能力声明）构成纵深防御第三层。

**监听事件与能力映射**（Windows/CPython 实测验证）：

| 事件                                                                                                     | 能力映射                                                                      |
| -------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `open` / `io.open`（读模式）                                                                             | `filesystem:read`                                                             |
| `open`（写模式） / `os.remove` / `os.unlink` / `os.rmdir` / `shutil.rmtree` / `os.mkdir` / `os.makedirs` | `filesystem:write`                                                            |
| `os.system` / `subprocess.Popen` / `os.exec*` / `os.spawn*`                                              | `process:exec`                                                                |
| `socket.connect`                                                                                         | `network`（http 声明隐含允许 TCP 连接该 host；否则按 `tcp://host:port` 比对） |
| `socket.bind`                                                                                            | `network:server`                                                              |
| `sqlite3.connect`                                                                                        | `database:sqlite`                                                             |

**归属判定**：审计事件触发时遍历调用栈，定位 `plugins/<name>.py` 帧（去 `.py` 后缀）；`base_plugin` 等框架内置帧不计为插件来源；解释器内部路径（stdlib/site-packages/`__pycache__`）读取直接跳过（非插件业务）。栈中无插件帧 → 视为框架自身行为放行。

**授权判定**：复用 4.3.2 注册的能力集与 `check_filesystem`（含自属路径隐式豁免）/`check_network`/`check_process`/`check_database`，未注册/未声明一律拒绝（fail-closed）。

**模式 `AUDIT_HOOK_MODE`**：

| 模式              | 行为                                                                  |
| ----------------- | --------------------------------------------------------------------- |
| `off`             | 不安装钩子（零开销）                                                  |
| `observe`（默认） | 未授权行为聚合计数 + 后台线程写审计 JSONL，不阻断                     |
| `enforce`         | 未授权行为抛 `RuntimeError`（消息含插件名与建议声明）阻断，插件可捕获 |

**未授权行为可视化（管理后台统计页）**：`/api/admin/stats` 返回 `audit_violations`（按插件分组：`{plugin, total, details:[{capability, count, example}]}`）；统计页新增红色统计卡（**合计由前端完成**）与明细表（插件 / 建议声明 / 次数 / 事件样本），**建议声明点击即可复制**回 plugin.json——引导作者明确补齐声明。建议声明由 `suggest_for_action` 生成，与 10.7 安装期交叉校验共用同一生成器。

**实现约束**：hook 内零 IO（`threading.local` 递归防护防死循环）；审计写入走内存队列 + 后台线程，`flush_now()` 可同步落盘；插件重载/卸载时聚合清零（`clear_violations`）。

**配置预设联动**：`daily→observe` / `strict→enforce` / `lan-open→off`（`tools/config.py profile`）。

```bash
python tools/config.py set AUDIT_HOOK_MODE enforce   # 运维加固：未授权即阻断
```

**已知局限**：ctypes 直接发起原始系统调用可绕过（属安装期 high 风险已拦截）；`os.getenv`/`os.environ` 无 audit 事件（env 域仅安装期声明记录）。

---

### 10.9 HTTPS 支持（v4.5.0）

框架默认以 HTTP 启动（127.0.0.1 或配置的 HOST/PORT）。配置证书与私钥后自动切换 HTTPS：

- **配置方式**（`tools/config.py`，见 8.1）：

  ```
  python tools/gen_cert.py                          # 生成自签名证书到 data/certs/
  python tools/config.py set SSL_CERT_FILE data/certs/cert.pem
  python tools/config.py set SSL_KEY_FILE data/certs/key.pem
  ```
- **生效条件**：`SSL_CERT_FILE` 与 `SSL_KEY_FILE` 均非空且文件存在 → `app.run(ssl_context=(cert, key))`，启动日志打印 `https://host:port`；任一缺失/文件不存在回退 HTTP 并告警。
- **自签名证书**：仅限本机/可信局域网使用，浏览器会提示不受信任，需手动信任或导入证书；`--san IP:192.168.x.x` 可追加局域网访问地址（SAN 缺失时现代浏览器直接拒绝连接，工具默认已含 localhost/127.0.0.1）。
- **与安全配置联动**：启用 HTTPS 后可将 `SESSION_COOKIE_SECURE` 置 `True`（会话 Cookie 加 Secure 属性）；`strict` 配置预设建议配合 HTTPS 使用（见 8.1 profile）。
- **私钥安全**：`data/certs/` 已加入 `.gitignore`，私钥不提交版本库。

---

### 10.10 插件数据配额（v4.9.1，声明模型，防恶意写盘）

配额是运行时审计钩子的**纵深防御第四层**（承接 10.8）——即使插件通过安装期审查，其运行时写盘总量仍受框架管控，防止恶意或失控插件无限写盘。v4.9.0 引入全局单插件默认配额，v4.9.1 升级为 **capabilities 声明模型**：插件显式向框架申请存储空间，框架据此授权并执行。

**配额来源优先级**：

```
插件 capabilities `storage:limit:<size>` 声明 > 全局 `PLUGIN_DATA_LIMIT_MB`（默认 50，0=无限制）
```

- `storage:limit:<size>`：纯数字=MB，或带单位 `mb` / `m` / `gb` / `g`（须 > 0）；非法声明安装期告警不拒绝（开放集合，语义见 10.7 能力目录）。
- `PLUGIN_DATA_LIMIT_MB`：全局单插件默认配额，`0`=禁用（插件不声明时按此执行）。

**配额作用目录**（`core/quota._plugin_quota_dirs` 推导）：

- `plugins/data/<name>/` 与 `plugins/temp/<name>/`——插件自属目录，**始终计入**；
- 插件 `filesystem:write` 声明的外部路径（相对项目根归一化，`**` 通配剥离为目录前缀）——覆盖 `plugins/` 外
  自定义存储目录（如 `uploads/`，描述文件声明 `filesystem:write:uploads/**` 即纳入配额保护）。

**判定与行为**（与 `AUDIT_HOOK_MODE` 联动）：

- 写事件（open/io.open w/a/x 等）发生时，capabilities 授权判定通过后，检查目标是否落在配额作用目录
  （归一化前缀匹配）；目录总量 TTL 缓存（5 秒）避免每次 os.walk；
- `observe`：记录 `audit-warn` 审计（不阻断）；`enforce`：抛 `RuntimeError` 拒绝写入（fail-closed）。

**上传预检（联动上传）**：插件上传 API 在写文件前调用 `self.check_upload(size)`（base_plugin 封装
`core/quota.check_upload`，上传接口可一行接入）——现有用量 + 新文件大小 <= 限额则放行，否则返回 **413 + 剩余空间提示**；审计钩子写事件兜底拦截流式写入绕过。下载为读操作不占配额；批量下载打包（temp 下 zip）计入所属插件 temp 配额。

**后台可视化与在线清理**：`GET /api/admin/quota` + 系统管理页"插件空间"卡片（每插件配额/用量/剩余 + 全局总量行）；管理员可在线执行单插件空间清理（`POST /api/admin/plugins/<name>/purge-data`，scope=`temp`/`all`，含配额缓存失效，v4.10 M6-Extra）——`temp` 仅清临时目录，`all` 级联清理数据目录与 `filesystem:write` 声明写目录（离线等价物见 14.8）。

**示例**：官方示例 `async_file_demo` 声明 `storage:limit:10mb` 并演示上传预检（413 + 剩余空间）与配额状态页。

**边界**：配额为运行时资源管控，**不替代安装期静态审查**（10.6/10.7）；插件写框架 `data/` 区域仍须声明 `filesystem:write`（10.7 现有机制）。

---

### 10.11 全局总量配额与后台空间管理（v4.9.2）

在单插件配额之上增加**框架级总量防线**，防多插件合计写盘失控：

- **全局总量配额**：配置项 `PLUGIN_DATA_TOTAL_LIMIT_MB`（默认 0=无限制）约束**全部插件数据总和**（所有插件
  data/temp/声明写目录用量之和，TTL 缓存）；上传预检 `check_upload` 自动接线（单插件限额 + 全局总量双检查，
  超限 reason 分别为 `plugin_quota_exceeded` / `global_quota_exceeded`）；审计钩子写事件同样做全局维度检查
  （enforce 拒绝 / observe 记录"全部插件数据总量超限"）。
- **后台插件空间管理**：`GET /api/admin/quota`（管理端接口）返回 `{plugins: all_plugins_quota(),
  total: {limit_mb, usage_mb, remaining_mb}}`——系统管理页"插件空间"卡片按插件列出配额/用量/剩余
  （无限制显示"无限制"），底部全局总量行（全局上限 / 总用量 / 剩余）；配合 `purge-data` 在线清理入口
  （10.10）与离线 `tools/install_plugin.py uninstall --purge-data`（14.8）。

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

| 脚本                          | 覆盖内容                                                                                                                                                                                                                                                                                                                                                                                                          | 规模  |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- |
| `test_permission.py`          | 权限体系（游客/登录/管理员三层 + CSRF）                                                                                                                                                                                                                                                                                                                                                                           | 20 项 |
| `test_stage2.py`              | 安全加固回归                                                                                                                                                                                                                                                                                                                                                                                                      | 19 项 |
| `test_zip_slip.py`            | 插件包 zip slip 防路径穿越专项（`..`/绝对路径/盘符拒绝 + 正常落位）                                                                                                                                                                                                                                                                                                                                               | 19 项 |
| `test_pack_meta.py`           | 插件包描述一致性（一致/缺失兜底/冲突拒绝/动态 name 不误伤/落盘对齐）+ pip_dependencies（v4.10）                                                                                                                                                                                                                                                                                                                   | 22 项 |
| `test_reload_race.py`         | 热加载重载竞态回归（test client，20 轮重载后会话保持，验证 auth 会话原子写）                                                                                                                                                                                                                                                                                                                                      | 1 项  |
| `test_meta_e2e.py`            | 插件包元信息端到端（上传/冲突/已存在/update 刷新/降级拒绝/require 拒绝，隔离目录模式可重复运行）                                                                                                                                                                                                                                                                                                                  | 10 项 |
| `test_frontend_zip_slip.py`   | 前端工具包安全解压 zip slip 专项（`..`/绝对路径/盘符拒绝 + 正常落位 + clean_static 更新清理 + 卸载资源清理）                                                                                                                                                                                                                                                                                                      | 21 项 |
| `test_frontend_chain.py`      | 前端工具上传/更新/卸载端到端（含页面/静态资源渲染、clean_static、413 上传大小限制）                                                                                                                                                                                                                                                                                                                               | 23 项 |
| `test_admin_api.py`           | 管理端 API 单测（system/info、plugins、stats、logs、factory-reset scope 校验、上传 413/400、空间管理、能力预览两段式、单插件空间清理 purge-data v4.10、网络与访问页接口 v4.11）                                                                                                                                                                                                                                   | 69 项 |
| `test_factory_reset.py`       | Factory Reset 范围测试（部分/全部删除与保留、内置插件保护、插件数据目录清理 v4.10 M6-Extra、空/非法 scope 无副作用）                                                                                                                                                                                                                                                                                              | 39 项 |
| `test_error_pages.py`         | 统一错误码页面渲染（404/405 真实触发 + 400/401/403/500 模板，双环境无 auth/带 auth）                                                                                                                                                                                                                                                                                                                              | 12 项 |
| `test_package_sign.py`        | 插件包完整性校验与签名专项（篡改/加料/缺失检测、签名验证、strict/warn/off 模式、路由集成、配公钥后签名端到端（v4.17.1）                                                                                                                                                                                                                                                                                                                        | 25 项 |
| `test_plugin_cleanup.py`      | 插件卸载 installed_files 清单专项（多 .py 包安装清单完整/卸载全清/clean_old 更新清理/越界路径防御）                                                                                                                                                                                                                                                                                                               | 23 项 |
| `test_frontend_permission.py` | 前端工具访问控制（三层权限 + 改权限 API 鉴权/边界 + 静态资源一致 + update 保留 permission）                                                                                                                                                                                                                                                                                                                       | 25 项 |
| `test_tools_ops.py`           | 开发运维工具回归（backup 创建/恢复、reset 范围、config 设置/非法值/unset）                                                                                                                                                                                                                                                                                                                                        | 19 项 |
| `test_page_router.py`         | 大插件多模板（页面路由 page=True：主入口自动检测、dict/Response 分发、路径参数注入、正斜杠模板名、旧式 page() 兼容）+ 纯 API 无 name 插件调试页回归                                                                                                                                                                                                                                                               | 21 项 |
| `test_framework_fixes.py`     | 框架小修复（v4.2.1）：public_page 豁免（公开页面免登录 200 / 普通插件页面守卫 302）+ plugin_common.js CSRF 单值注入静态断言 + 调试页权限（v4.10）                                                                                                                                                                                                                                                                 | 12 项 |
| `test_file_transfer.py`       | 文件传输强化（v4.2.2）：全局 413 / 插件级 max_upload_size 预检 / route 级 max_upload 覆盖 / 中文名下载 / 下载统计 / Range / on_ready 顺序                                                                                                                                                                                                                                                                         | 12 项 |
| `test_security.py`            | 系统安全回归（v4.3.0）：安全响应头注入与开关 / 指纹头移除 / Cookie HttpOnly+SameSite+Secure 联动 / 会话空闲超时 / 登录失败锁定三档（ip_username/username/off）+ 通用 429 + 成功重置 + 解封（v4.5.1）                                                                                                                                                                                                              | 45 项 |
| `test_plugin_scan.py`         | 插件静态扫描回归（v4.3.1）：扫描器单元（危险导入/调用/混淆/范围提取/别名归因）/ 插件包扫描 / 前端 HTML 扫描 / enforce 门禁集成（拒绝 400 + 附报告 + 未落盘 + 真实项目未污染）/ 配置预设三套                                                                                                                                                                                                                       | 35 项 |
| `test_capabilities.py`        | 插件能力声明回归（v4.3.2）：解析器（合法/非法/未知域/裸 * 拒绝）/ 匹配语义（路径前缀递归/URL host·path·端口/子域通配/tcp/env）/ 交叉校验（隐式豁免/跨插件越界/建议声明/unused）/ 运行时授权 API（fail-closed/process 细粒度）/ 安装链路集成（enforce 拒绝与放行/响应附摘要/loader 注册）/ base_plugin data API + hello_plugin 示例端到端 / **storage 域解析与目录推导（v4.9.1）** + **framework 域三档（v4.15）** | 70 项 |
| `test_root_domain.py`         | Root 域与市场骨架（v4.15）：framework 三档 read/manage/core / 核心路径判定 / root 写放行与拒绝 / 服务层 require_manage / 市场写 core 拒绝 / 插件级更新源                                                                                                                                                                                                                                                          | 18 项 |
| `test_framework_manifest.py`  | 框架目录清单统一（v4.15.1）：selfcheck/update/backup 复用同一对象 + CORE_FILES/CORE_DIRS 完整性 + Root 域路径判定边界（含插件内容/自属目录豁免）+ is_user_data_path 语义 + BACKUP_ITEMS 派生                                                                                                                                                                                                                      | 54 项 |
| `test_root_demo.py`           | 示例插件 root_demo（v4.15.1）：plugin.json 声明一致 + framework:core 授权/写核心放行/读核心/对照拒绝/自属豁免/模块可加载                                                                                                                                                                                                                                                                                          | 19 项 |
| `test_audit_hook.py`          | 运行时审计钩子回归（v4.4.0）：事件映射（open 读写/删除族/sqlite/socket）/ 栈定位（plugins 帧/框架放行/嵌套归因）/ observe 聚合（按插件/建议声明/事件样本）/ enforce 阻断（异常传播/授权放行/自属豁免/fail-closed）/ 隔离集成（真实钩子+栈归因端到端/stats 按插件分组/重载清零/审计落盘/未污染）                                                                                                                   | 38 项 |
| `test_update_checker.py`      | 版本检查推送（v4.8.0）：版本比较（parse_version/is_newer）/ 用户数据路径判定（v4.9.2 补 users/locales）/ zip slip 防护 / archive 校验链（sha256 必选 + 签名可选）/ 数据源缓存 TTL / 数据源结构校验 / 自更新签名验签（v4.17.1）                                                                                                                                                                                                                | 50 项 |
| `test_plugin_updates.py`      | 插件级更新源签名（v4.15/v4.17.1）：未配公钥放行 / 有效签名通过 / 篡改·无签名·错误公钥·公钥文件不存在拒绝 / 未声明更新源 | 8 项 |
| `test_release_sign.py`        | 发布签名联动（v4.17.1）：release --sign 产出含 signature / 配公钥验证通过 / 篡改拒绝 / 签名失败不写缓存 / 错误公钥拒绝 | 5 项 |
| `test_i18n.py`                | i18n（v4.9.0）：语言包加载 / 查找链（插件合并与覆盖）/ 语言解析优先级 / 切换路由 / 模板渲染（中英） / 缺省回退 / 参数插值                                                                                                                                                                                                                                                                                         | 29 项 |
| `test_data_limit.py`          | 插件数据配额（v4.9.0-4.9.2）：路径判定（data/temp/边界）/ 用量统计 / enforce 超限拒绝 / observe 记录 / TTL 缓存刷新 / 0 禁用 / **storage:limit 覆盖全局 / write 声明目录推导（uploads/ 场景）/ check_upload 预检 / 全局总量配额**                                                                                                                                                                                 | 32 项 |
| `test_network.py`             | 网络与访问（v4.11/v4.12）：局域网地址发现/端口三级优先/访问地址组合/mDNS 集成/**HTTP→HTTPS 308 跳转与 Secure Cookie 四态（v4.12）**                                                                                                                                                                                                                                                                               | 41 项 |
| `test_mdns.py`                | mDNS 服务注册（v4.11）：ServiceInfo 构造（新旧参数兼容）/ 启动停止幂等 / 依赖缺失降级                                                                                                                                                                                                                                                                                                                             | 22 项 |
| `test_ip_watcher.py`          | IP 变化检测（v4.11）：快照比较 / 首次不报 / 启停与间隔控制                                                                                                                                                                                                                                                                                                                                                        | 15 项 |
| `test_desktop_launcher.py`    | 桌面启动器（v4.11/v4.12）：配置写入/访问信息生成/启动与端口解析/**HTTPS 复选框与证书自动生成（v4.12）**                                                                                                                                                                                                                                                                                                           | 36 项 |
| `test_setup.py`               | 首次运行向导 + 强制改密（v4.10 M4）：/setup 路由与标记 / 改密校验与踢会话 / must_change_pwd 标记                                                                                                                                                                                                                                                                                                                  | 17 项 |
| `test_register.py`            | 邀请码自助注册（v4.10 M5）：邀请码生成消费 / pending 拦截 / 审核 API                                                                                                                                                                                                                                                                                                                                              | 25 项 |
| `test_scaffold_tools.py`      | 脚手架 + 离线安装/卸载闭环（v4.10 M6）：scaffold 骨架 / install_plugin 安装升级降级拒绝 / uninstall 清理                                                                                                                                                                                                                                                                                                          | 53 项 |
| `test_stats.py`               | 数据统计洞察（v4.14）：时间桶 + 访问画像双维数据模型 / dashboard 总览化 / 14 天趋势 + 错误 Top + 画像卡                                                                                                                                                                                                                                                                                                           | 55 项 |
| `test_selfcheck.py`           | 启动完整性自检（v4.15）：CORE_FILES 完整性 / 时区（tzdata）探测 / 完整自检                                                                                                                                                                                                                                                                                                                                        | 14 项 |
| `test_events.py`              | 事件总线（v4.16）：priority / once / off / weakref 失效清理 / 绑定方法强引用 / async 非阻塞 / 异常隔离 / 内置事件                                                                                                                                                                                                                                                                                                 | 11 项 |
| `test_dependency.py`          | 依赖解析（v4.16）：dep_spec 解析 / semver 含预发布 / Kahn 拓扑 / 环 / 缺失排除                                                                                                                                                                                                                                                                                                                                    | 11 项 |
| `test_plugin_events.py`       | BasePlugin 事件集成 + 示例演示（v4.16）：scheduler_demo 事件订阅/定时/手动发布/清空/清理防泄漏 + dependent_demo 跨插件事件来源归因                                                                                                                                                                                                                                                                                | 28 项 |
| `test_device.py`              | 设备检测 + 移动端模板分发（v4.17）：UA 分类 / 配置开关 / resolve_template 分发 / 公开页移动端模板 / BasePlugin 移动端命名空间                                                                                                                                                                                                                                                                                     | 20 项 |

```bash
cd FlaskToolkit   # 在项目根目录执行
python tests/test_permission.py       # 20 项（权限体系）
python tests/test_stage2.py           # 19 项（安全加固回归）
python tests/test_zip_slip.py         # 19 项
python tests/test_pack_meta.py        # 22 项
python tests/test_reload_race.py      # 1 项
python tests/test_meta_e2e.py         # 10 项（隔离目录模式）
python tests/test_frontend_zip_slip.py# 21 项
python tests/test_frontend_chain.py   # 23 项（前端工具链路，隔离目录）
python tests/test_admin_api.py        # 69 项（管理端 API + purge-data + 网络接口，隔离目录）
python tests/test_factory_reset.py    # 39 项（Factory Reset 范围，隔离目录）
python tests/test_error_pages.py      # 12 项（错误码页面，隔离目录）
python tests/test_package_sign.py     # 25 项（完整性校验/签名/配公钥签名端到端，隔离目录）
python tests/test_plugin_cleanup.py    # 23 项（插件卸载 installed_files 清单，隔离目录）
python tests/test_frontend_permission.py # 25 项（前端工具访问控制，隔离目录）
python tests/test_tools_ops.py         # 19 项（backup/reset/config 运维工具，隔离目录）
python tests/test_page_router.py       # 21 项（大插件多模板页面路由 + 纯 API 无 name 插件调试页回归，隔离目录）
python tests/test_framework_fixes.py    # 12 项（public_page 豁免 + CSRF 单值注入 + 调试页权限，隔离目录）
python tests/test_file_transfer.py       # 12 项（文件传输强化，隔离目录）
python tests/test_security.py            # 45 项（系统安全回归 v4.3.0 + 解封，隔离目录）
python tests/test_plugin_scan.py           # 35 项（插件静态扫描回归 v4.3.1，隔离目录）
python tests/test_capabilities.py          # 70 项（插件能力声明回归 v4.3.2 + storage/framework 域，隔离目录）
python tests/test_root_domain.py         # 18 项（Root 域与市场骨架 v4.15，隔离目录）
python tests/test_framework_manifest.py   # 54 项（框架目录清单 v4.15.1，隔离目录）
python tests/test_root_demo.py            # 19 项（示例插件 root_demo v4.15.1，隔离目录）
python tests/test_audit_hook.py            # 38 项（运行时审计钩子回归 v4.4.0，隔离目录）
python tests/test_update_checker.py     # 50 项（版本检查推送回归 v4.8.0 + 自更新签名验签，隔离目录）
python tests/test_plugin_updates.py    # 8 项（插件级更新源签名 v4.15/v4.17.1，隔离目录）
python tests/test_release_sign.py      # 5 项（发布签名联动 v4.17.1，隔离目录）
python tests/test_i18n.py                  # 29 项（i18n 回归 v4.9.0，隔离目录）
python tests/test_data_limit.py            # 32 项（插件数据配额回归 v4.9.0-4.9.2，隔离目录）
python tests/test_network.py            # 41 项（网络与访问 v4.11 + 308 跳转/Secure 判定 v4.12，隔离目录）
python tests/test_mdns.py               # 22 项（mDNS 服务注册 v4.11，mock zeroconf，隔离目录）
python tests/test_ip_watcher.py         # 15 项（IP 变化检测 v4.11，隔离目录）
python tests/test_desktop_launcher.py   # 36 项（桌面启动器 v4.11 + HTTPS v4.12，隔离目录）
python tests/test_setup.py             # 17 项（首次运行向导 + 强制改密 v4.10，隔离目录）
python tests/test_register.py             # 25 项（自助注册 + 邀请码 + 审核 v4.10 M5，隔离目录）
python tests/test_scaffold_tools.py  # 53 项（M6 脚手架 + 离线安装/卸载闭环，subprocess 驱动 CLI，隔离目录）
python tests/test_stats.py               # 55 项（数据统计洞察 v4.14，隔离目录）
python tests/test_selfcheck.py           # 14 项（启动完整性自检 v4.15，隔离目录）
python tests/test_events.py              # 11 项（事件总线 v4.16，隔离目录）
python tests/test_dependency.py          # 11 项（依赖解析 v4.16，隔离目录）
python tests/test_plugin_events.py       # 28 项（BasePlugin 事件集成 + 示例演示 v4.16，隔离目录）
python tests/test_device.py              # 20 项（设备检测 + 移动端模板分发 v4.17，隔离目录）
# 合计 43 个脚本（本地全量实测）
# （AirDrop 插件加载回归 test_airdrop_loader.py 8 项已移交 AirDrop 子项目维护，不入主仓库）
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
python tools/config.py profile <daily|strict|lan-open>   # 套用安全配置预设（v4.3.1）
```

主要可配置项：

| 配置项                       | 默认值                            | 说明                                                                                                                                           |
| ---------------------------- | --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `HOST`                       | 127.0.0.1                         | 服务绑定地址（FLASKTOOLKIT_HOST 优先）                                                                                                         |
| `PORT`                       | （自动探测）                      | 服务端口（FLASKTOOLKIT_PORT 优先）                                                                                                             |
| `DEBUG`                      | false                             | 调试模式（FLASKTOOLKIT_DEBUG 优先）                                                                                                            |
| `UPLOAD_TEMP_DIR`            | BASE_DIR/temp                     | 上传临时目录                                                                                                                                   |
| `FRONTEND_TEMPLATE_DIR`      | BASE_DIR/templates/frontend_tools | 前端工具模板/静态资源目录                                                                                                                      |
| `FRONTEND_CONFIG_FILE`       | BASE_DIR/data/frontend_tools.json | 前端工具注册配置文件（v4.5.0 起位于 data/）                                                                                                    |
| `PLUGIN_CONFIGS_DIR`         | BASE_DIR/plugins/configs          | 插件配置目录                                                                                                                                   |
| `PLUGIN_TEMP_DIR`            | BASE_DIR/plugins/temp             | 插件临时目录                                                                                                                                   |
| `PLUGIN_CACHE_DIR`           | BASE_DIR/.plugin_cache            | 插件扫描缓存目录                                                                                                                               |
| `LOG_DIR`                    | BASE_DIR/logs                     | 日志目录                                                                                                                                       |
| `STATS_FILE`                 | BASE_DIR/data/stats.json          | 统计数据文件                                                                                                                                   |
| `STATS_RETENTION_DAYS`       | 30                                | 统计时间桶保留天数（v4.14，最小 7）                                                                                                            |
| `ACCESS_PROFILE_ENABLED`     | true                              | 访问画像开关（v4.14，关则仅计时间桶不采集画像）                                                                                                |
| `PACKAGE_MAX_UPLOAD_SIZE_MB` | 10                                | 插件包/工具包上传大小上限（MB）                                                                                                                |
| `MAX_UPLOAD_SIZE_MB`         | 100                               | 全局文件上传大小上限（MB，映射 MAX_UPLOAD_SIZE，MAX_CONTENT_LENGTH 兜底；插件级/route 级可继续收紧，见 10.3）                                  |
| `PLUGIN_STRICT_MODE`         | false                             | 严格模式：on_load 依赖检查降级由 on_ready 钩子延后（所有插件加载完成后执行，见 5.3）                                                           |
| `PACKAGE_INTEGRITY_MODE`     | warn                              | 完整性校验模式（strict/warn/off）                                                                                                              |
| `PLUGIN_SCAN_MODE`           | report                            | 插件安装静态扫描门禁（off/report/enforce，见 10.6，v4.3.1）                                                                                    |
| `PLUGIN_PUBLIC_KEY_PEM`      | （空）                            | 插件签名公钥路径                                                                                                                               |
| `UPDATE_FEED_URL`            | （GitHub raw）                    | 版本检查数据源地址（v4.8.0）                                                                                                                   |
| `UPDATE_CHECK_ENABLED`       | true                              | 启动时版本检查开关（v4.8.0）                                                                                                                   |
| `UPDATE_CHECK_INTERVAL`      | 24                                | 版本检查间隔（小时，v4.8.0）                                                                                                                   |
| `UPDATE_PUBLIC_KEY_PEM`      | （空）                            | 版本数据源签名公钥路径（配置后强制验签，v4.8.0）                                                                                               |
| `LANGUAGE`                   | zh-CN                             | 系统显示语言（v4.9.0，可选值由 locales/ 语言包决定，Cookie `lang` 可覆盖）                                                                     |
| `SYSTEM_NAME`                | FlaskToolkit                      | 系统显示名称（v4.7.0，仅装饰，不影响内部标识）                                                                                                 |
| `SYSTEM_VERSION_LABEL`       | v4.17.0                           | 系统版本显示标签（v4.7.0，仅装饰，升级框架时建议同步更新）                                                                                     |
| `PLUGIN_DATA_LIMIT_MB`       | 50                                | 单插件数据目录配额（MB，0=禁用，v4.9.0 见 10.10）                                                                                              |
| `PLUGIN_DATA_TOTAL_LIMIT_MB` | 0                                 | 全部插件数据总量配额（MB，0=无限制，v4.9.2 见 10.11）                                                                                          |
| `MDNS_ENABLED`               | false                             | mDNS 服务注册开关（v4.11，需重启生效，需 pip install zeroconf）                                                                                |
| `MDNS_HOSTNAME`              | flasktoolkit                      | mDNS 主机名（v4.11，服务以 <name>.local 可达）                                                                                                 |
| `IP_WATCH_INTERVAL`          | 30                                | IP 变化检测间隔（秒，0=关闭，v4.11）                                                                                                           |
| `SESSION_COOKIE_SECURE`      | （自动）                          | 会话/CSRF Cookie Secure 属性（v4.12，None=自动：HTTPS 直连或反代外部 https 时自动 true，纯 HTTP 局域网自动 false；true 强制 / false 强制关闭） |
| `TRUST_PROXY_HEADERS`        | false                             | 反向代理头信任（v4.12，TLS 在 Nginx 等代理终止时开启；信任 X-Forwarded-Proto/For/Host，恢复客户端 IP 归因；仅可信代理后方可开启）              |
| `EXTERNAL_HOST`              | （空）                            | 外部域名（v4.12，反向代理场景可选；分享地址/二维码用它，不设则自动用本机 IP/主机名，需与证书 SAN 一致）                                        |
| `EXTERNAL_PORT`              | 0                                 | 外部端口（v4.12，反向代理监听端口；分享地址/二维码用它，0=内部端口）                                                                           |
| `EXTERNAL_SCHEME`            | （空）                            | 外部访问协议（v4.12，空=按 SSL_CERT_FILE 自动判断；反向代理 TLS 终止场景设 https，使分享链接/二维码/横幅/桌面启动器显示 https）                |
| `MOBILE_ENABLED`             | true                              | 移动端页面分离开关（v4.17，关则全部回退桌面端模板，见 5.10）                                                                                   |
| `FORCE_MOBILE`               | false                             | 强制手机端（v4.17，调试/测试用，见 5.10）                                                                                                      |

示例：

```bash
python tools/config.py set PACKAGE_MAX_UPLOAD_SIZE_MB 20
python tools/config.py set PACKAGE_INTEGRITY_MODE strict
python tools/config.py set HOST 0.0.0.0
python tools/config.py set PORT 8080
python tools/config.py set DEBUG true
python tools/config.py profile strict    # 一键套用运维加固预设
```

## 十四、开发运维工具与启动自检

| 工具                        | 职责                               | 详见 |
| --------------------------- | ---------------------------------- | ---- |
| `tools/config.py`           | 配置项查看/设置/预设               | 13   |
| `tools/i18n_status.py`      | i18n 翻译进度报告 / 新语言包脚手架 | 15.5 |
| `tools/package.py`          | 插件包打包/签名/校验               | 10.5 |
| `tools/scan.py`             | 插件静态扫描 CLI                   | 10.6 |
| `tools/gen_cert.py`         | 自签名证书生成                     | 14.4 |
| `tools/update.py`           | 双后端更新（git/archive）          | 14.5 |
| `tools/release.py`          | 版本发布工具链                     | 14.6 |
| `tools/scaffold.py`         | 插件/前端工具脚手架                | 14.7 |
| `tools/install_plugin.py`   | 离线安装/卸载/清理                 | 14.8 |
| `tools/backup.py`           | 手动备份/恢复                      | 14.2 |
| `tools/reset.py`            | 深度重置（服务停止态）             | 14.3 |
| `tools/desktop_launcher.py` | 桌面启动器（GUI）                  | 14.9 |
| `core/selfcheck.py`         | 启动完整性自检                     | 14.1 |

### 14.1 启动完整性自检（core/selfcheck.py）

框架每次启动时执行完整性自检：

- 校验核心文件/目录存在、第三方依赖（flask/flask_cors/apscheduler/watchdog）可导入、数据目录可写；时区数据可用性（v4.15：APScheduler 3.11 改用标准库 zoneinfo，Windows 缺 tzdata 时 `ZoneInfoNotFoundError` 使启动崩溃——自检主动探测，缺失即致命报错并提示 `pip install tzdata`）；
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

备份内容：`plugins/configs`、`plugins/status.json`、`plugins/data`、`data`（统计/审计/用户配置/前端工具清单）、`logs`。

说明：`locales/` 为框架内置 i18n 语言包（随框架版本一致）、`users/` 为 AI 助手本地数据（非框架数据），均不在备份范围。

### 14.3 深度重置（tools/reset.py）

在服务停止状态下直接操作文件系统完成重置，可绕过服务运行时文件被占用/锁定的问题（呼应 Factory Reset 的手动备份与运行时限制）：

```bash
python tools/reset.py list                            # 列出可重置范围
python tools/reset.py reset <scope> [scope...]        # 重置指定范围
python tools/reset.py reset all                       # 全部重置
python tools/reset.py reset all --auto-backup         # 先自动备份再全部重置
```

范围与 Factory Reset 一致：`plugins` / `frontend_tools` / `stats_logs` / `sessions` / `temp` / `builtin` / `all`。

- 服务运行检测读取用户配置 `HOST/PORT`（`tools/config.py` 可设，默认 127.0.0.1:5000），仅提示不强制。
- `locales/` 语言包（含用户扩展语言包）与用户配置同类，深度重置保留，与 Factory Reset 语义一致。

### 14.4 自签名证书生成（tools/gen_cert.py，v4.5）

调用系统 openssl 生成自签名证书/私钥对（默认 RSA 2048，输出 `data/certs/`，已加入 .gitignore 不提交版本库）：

```bash
python tools/gen_cert.py                         # 生成 cert.pem / key.pem（默认含 localhost/127.0.0.1 SAN）
python tools/gen_cert.py --san IP:192.168.1.10   # 追加局域网访问地址（SAN 缺失时现代浏览器直接拒绝连接）
```

生成后配置启用 HTTPS（见 10.9）：`tools/config.py set SSL_CERT_FILE data/certs/cert.pem` + `SSL_KEY_FILE` 配对；桌面启动器的 HTTPS 复选框缺证书时也会自动调用本工具生成。

### 14.5 双后端更新（tools/update.py，v4.8）

面向部署方：从 Release 资产升级框架，支持 git / archive（离线内网）双后端，均保留用户数据（`USER_DATA_PATHS` 清单：data / plugins/configs / plugins/data / plugins/temp / logs 等）：

```bash
python tools/update.py check                 # 检查新版本（changelog.json 数据源，24h TTL）
python tools/update.py backup                # 更新前备份当前框架
python tools/update.py apply                 # 应用更新（自动探测 git/archive 后端）
python tools/update.py apply --backend archive --dry-run   # 指定后端 + 演练
python tools/update.py rollback              # 回滚到最近备份
python tools/update.py selfcheck             # 更新后运行启动自检
```

- **git 后端**：fetch/stash/reset 到目标版本，selfcheck 失败自动回滚（开源环境 gitignore 天然保留配置）。
- **archive 后端**：下载 zip 校验 sha256（必选）+ 签名（可选，配置 `UPDATE_PUBLIC_KEY_PEM`），显式跳过用户数据路径后替换，失败自动回滚。

### 14.6 发布工具链（tools/release.py，v4.8，发布者使用）

```bash
python tools/release.py bump 4.12.1          # 同步版本号（FRAMEWORK_VERSION / SYSTEM_VERSION_LABEL / test 断言 / README 徽章）
python tools/release.py build                # 构建精简运行包 + 写 changelog.json（--sign 生成签名 feed）
python tools/release.py build --full         # 全量包（含 tests/documents/examples，供归档审计）
python tools/release.py build --include src:dest   # 定制包（叠加企业私有插件/文档）
```

- `build` 默认**精简运行包**（仅运行必需：core/routes/plugins 内置/templates/static/locales），用户数据路径清单始终保留；
- `changelog.json` 是发布强制同步点（latest_version/sha256/download_url/changes），须随 Release 一起提交推送。

### 14.7 插件脚手架（tools/scaffold.py，v4.10）

生成标准插件骨架，产出目录可直接 `tools/package.py pack` 打包分发：

```bash
python tools/scaffold.py backend my_plugin [--with-static] [--with-templates]   # 后端插件（plugin.json + 主 .py + 可选资源）
python tools/scaffold.py frontend my_tool [--with-static]                      # 前端工具（config.json + 入口 html + 可选 static）
```

### 14.8 离线安装/卸载与单插件空间清理（tools/install_plugin.py，v4.10）

不启动框架服务时手动安装/卸载插件包（离线部署、交付前自测场景）：

```bash
python tools/install_plugin.py backend my_plugin.zip          # 安装/更新后端插件（--update 升级，拒绝降级）
python tools/install_plugin.py frontend my_tool.zip           # 安装/更新前端工具
python tools/install_plugin.py uninstall backend my_plugin    # 离线卸载（按 installed_files 清单删除，内置插件受保护）
python tools/install_plugin.py uninstall frontend my_tool --purge-data   # 卸载并级联清理数据/临时/声明写目录
python tools/install_plugin.py list                           # 列出已安装插件与前端工具
```

- 安装链路与在线一致：完整性校验 → 描述一致性 → 框架版本门槛 → 静态扫描门禁 → 安全解压 + installed_files 落盘；缺失 pip 依赖仅提示并附 `pip install` 命令（不自动安装）；
- `--base` 指定框架根目录（默认自动探测）；离线卸载不执行插件 `on_uninstall` 钩子（框架未运行）；
- `--purge-data` 与后台 `purge-data` API（10.10）语义一致：临时目录 + 数据目录 + capabilities `filesystem:write` 声明写目录。

### 14.9 桌面启动器（tools/desktop_launcher.py，v4.11）

面向"免命令行"普通用户的 tkinter GUI（Python 标准库，双击即用，subprocess 解耦不 import 框架核心）：

```bash
python tools/desktop_launcher.py             # 打开 GUI：访问模式（仅本机/局域网）/ 端口 / 启动停止 / 地址列表 / 复制 / 打开浏览器
python tools/desktop_launcher.py --shared    # CLI：局域网共享模式启动
python tools/desktop_launcher.py --https     # CLI：启用 HTTPS（缺证书自动调用 gen_cert.py 生成）
python tools/desktop_launcher.py --smoke     # 无 GUI 冒烟测试模式
```

GUI 内含 **HTTPS 复选框**（按现有配置预选，勾选后自动生成/配置证书，v4.12）；二维码展示需 `qrcode` + `PIL` 可选库（缺失仅隐藏二维码区）。

## 十五、国际化（i18n，v4.9.0）

### 15.1 语言包格式

`locales/<lang>.json` 键值对，**中文原文即 key**（缺省回退天然中文，英文等语言提供翻译映射）：

```json
{ "__name__": "English", "登录": "Sign In", "插件管理": "Plugins" }
```

- `__name__`：语言自称（界面语言切换入口显示，缺省回退语言代码）。
- 扩展语言 = 在 `locales/` 新增 `<lang>.json` 即可，`available_languages()` 自动发现。
- 语言代码白名单校验（仅允许真实存在的语言包），防路径注入。

### 15.2 查找链与 t()

查找链：插件语言包（`plugins/<name>/locales/<lang>.json`，可覆盖框架词条）
→ 框架语言包（`locales/<lang>.json`）→ key 原文（缺省回退）。

- 模板：`{{ t('登录') }}`（Jinja 全局注入，无需传参）
- 后端：`from core import i18n; tr = i18n.make_translator(i18n.get_lang()); tr('登录')`
- 前端：`window.T('登录')`（翻译表由服务端以 `t_json` 注入 `window.__I18N`）
- 参数插值：`t('请求体超过大小限制', size=50)` → `{size}` 占位符替换

### 15.3 语言选择

优先级：**Cookie `lang` > 用户配置 `LANGUAGE` > 默认 zh-CN**。

- 切换接口：`GET /lang/<code>?next=<path>`（设置 `lang` Cookie，站内相对路径重定向防开放跳转）
- 入口：登录页右上角 + 后台页眉（自动列出 `available_langs` 中非当前语言）
- 配置：`python tools/config.py set LANGUAGE en`（启动显示语言全局默认）

### 15.4 插件国际化

插件可在插件包内携带 `locales/<lang>.json`，安装后自动合并进查找链（插件词条覆盖框架词条）；
插件模板直接使用 `{{ t('...') }}` 即随框架语言联动。框架不翻译插件内容，由插件作者自行提供语言包。
官方示例 `corp_tools`（v4.9.1）演示完整插件多语言：自带 `locales/en.json`（含 `__name__`），4 个模板
`{{ t('...') }}` 迁移 + 后端消息经 `_tr()`（`i18n.make_translator(i18n.get_lang())`）+ 前端 `window.T`
（模板内注入 `window.__I18N = {{ t_json | tojson }}`）；页面顶部自动出现语言切换入口
（`/lang/<code>?next=<当前路径>`）。

### 15.5 各页面语言切换 + 翻译工具（v4.15.4）

**各页面统一语言切换入口**：所有页面（首页、后台各页、插件默认/API 文档页、注册页、全部错误页）均已加入语言切换入口——深色导航页为统一下拉（`_lang_switch.html`），浅色页面为平铺链接；切换均走 `/lang/<code>?next=<当前路径>`（15.3）。

**翻译工具 `tools/i18n_status.py`**：以 `locales/en.json` 为完整基准报告各语言翻译进度与贡献者，供翻译贡献者对齐缺失词条。

```bash
python tools/i18n_status.py                        # 报告全部语言翻译进度（可读表格）
python tools/i18n_status.py --json                 # 机器可读 JSON 输出
python tools/i18n_status.py --check                # 校验语言包完整性（缺 key / 多余 key / 结构错误）
python tools/i18n_status.py <lang>                 # 只看指定语言
python tools/i18n_status.py --create <lang> --name "语言名"   # 基于 en.json 模板创建新语言包
```

- `--create` 基于 `en.json` 一键脚手架新语言包（内置 `en` / `zh-CN` 受保护，不可创建/修改）。
- 语言包可选 `__contributors` 元信息字段（固定 `__` 前缀，与 `__name__` 一致不参与翻译对照），`i18n_status` 展示各语言包贡献者。
- 回归断言扫描全部框架模板，保证模板中任一中文字符串 key 必被语言包覆盖（见 12 章 `test_i18n`）。

---

## 附录 A：常见问题（FAQ）

> 按主题分节；每题给出症状、原因与处理步骤。历史版本 FAQ 归档于 `documents/archive/`。

### A.1 安装与启动

**A.1.1 启动自检失败、服务无法启动**

- 症状：启动输出 `selfcheck` 失败并中止（`sys.exit(1)`）。
- 原因：核心文件缺失（`CORE_FILES`）或第三方依赖（flask / flask_cors / apscheduler / watchdog）不可导入。
- 处理：按提示 `pip install -r requirements.txt`；检查项目文件完整性（勿删除 core/、routes/ 等运行必需目录）；数据目录写权限问题仅告警不阻断。

**A.1.2 端口被占用导致启动失败或端口不符**

- 处理：默认端口自动探测回落（被占用时自动换端口并打印实际地址）；显式指定用 `FLASKTOOLKIT_PORT` 环境变量或 `python tools/config.py set PORT <port>`。

**A.1.3 插件未加载且提示缺少第三方依赖**

- 症状：后台插件列表中插件缺失，日志/响应附 `pip install <pkg>` 提示（v4.10 `pip_dependencies`）。
- 处理：按提示安装依赖后重载；框架**不自动安装**依赖（设计如此，避免供应链风险）。

### A.2 权限与登录

**A.2.1 插件接口返回 401 未登录**

- 原因：接口未声明 `@permission_required("public")` 时默认"仅登录"。
- 处理：给公开接口补 public 声明，或用登录态访问（未登录访问会跳转登录页）。

**A.2.2 写请求返回 403 CSRF 校验失败**

- 原因：缺少 CSRF 双提交校验头。
- 处理：前端引入 `plugin_common.js`（自动注入 `X-CSRF-Token`，值 = `csrf_token` Cookie）或手动注入该头；GET/HEAD/OPTIONS 不需要 CSRF 头。

**A.2.3 登录提示"用户名或密码错误"**

- 原因：默认管理员 `admin / admin123`；v4.10 起首次登录**强制改密**（登录响应 `must_change_pwd`，后台弹改密窗）。
- 处理：管理员账号在 `plugins/configs/auth.json` 修改；如已改密请用新密码；忘记密码可在服务停止态直接编辑该文件还原。

**A.2.4 登录被锁定（HTTP 429）**

- 原因：连续失败达到 `LOGIN_MAX_ATTEMPTS`（默认 5），锁定 `LOGIN_LOCK_SECONDS`（默认 900 秒），维度 `ip_username`/`username`。
- 处理：等待锁定期满；管理员在 user_manage 用户管理页一键解封（v4.5.1）；锁定计数仅存内存，重启即清零。

**A.2.5 登录提示"账号待管理员审核"**

- 原因：v4.10 M5 邀请码自助注册——无邀请码注册进入 `pending` 待审状态。
- 处理：管理员在 user_manage 审核通过；或持邀请码注册（`?code=` 自动填充）即时 active。

### A.3 插件开发与安装

**A.3.1 插件 API 返回 404**

- 插件未加载：检查是否启用、依赖是否满足、`pip_dependencies` 是否缺失；
- 路径不匹配：确认 `routes` 中 path 与请求一致（含参数格式）；
- 页面路由未生效：大插件多模板需 `page=True` 并放模板到 `templates/plugins/<name>/`（见 5.5.1）。

**A.3.2 插件安装被拒绝（400 附 scan_report / capabilities missing）**

- 原因：`PLUGIN_SCAN_MODE=enforce` 下检出高风险（high > 0）或 `missing` 非空（Deny by Default）。
- 处理：按响应中的 `suggested` 建议声明补齐 `capabilities`（可整段复制回 plugin.json）后重新打包；确属误报可在 `report` 模式放行后人工复核（不建议关扫描）。

**A.3.3 插件包安装报完整性校验失败**

- 原因：包缺 `manifest.json` 且 `PACKAGE_INTEGRITY_MODE=strict`，或包内容被篡改/加料。
- 处理：用 `python tools/package.py pack` 重新打包（自动生成 manifest）；校验模式见 10.5。

**A.3.4 插件安装提示框架版本不足**

- 原因：插件 `require_framework_version` 高于当前框架版本。
- 处理：升级框架（`tools/update.py apply`）或选用兼容版本插件。

**A.3.5 插件热重载未生效**

- 处理：确认文件监听运行（watchdog 依赖）；修改后等待增量重载；`plugins/status.json` 中插件状态为启用；如改的是描述文件/依赖声明，需手动重载或重启。

### A.4 文件上传与数据配额

**A.4.1 上传插件包/工具包返回 413**

- 原因：超过 `PACKAGE_MAX_UPLOAD_SIZE_MB`（默认 10MB）。
- 处理：`python tools/config.py set PACKAGE_MAX_UPLOAD_SIZE_MB 20`（需重启生效）。

**A.4.2 插件数据上传 413（配额超限）**

- 原因：`check_upload` 预检发现超出插件配额（`plugin_quota_exceeded`）或全局总量配额（`global_quota_exceeded`）。
- 处理：提高 `storage:limit` 声明或 `PLUGIN_DATA_LIMIT_MB` / `PLUGIN_DATA_TOTAL_LIMIT_MB`；或清理旧数据（后台插件空间卡片/`purge-data`）。

**A.4.3 enforce 模式下插件写文件被拒（RuntimeError）**

- 原因：`AUDIT_HOOK_MODE=enforce` 时未授权/超配额写操作被运行时拦截（消息含插件名与建议声明）。
- 处理：按建议声明补 `capabilities`；配额超限按 A.4.2 处理。

### A.5 安全与 HTTPS

**A.5.1 访问 http:// 被 308 跳转到 https://**

- 原因：直连 HTTPS 模式（v4.12）下框架自动在主端口+1 起 308 跳转（保留 POST 方法与 body）——这是设计行为，旧 `http://` 链接不会死。
- 处理：无需处理；反向代理场景跳转由 Nginx 负责（见 3.4）。

**A.5.2 浏览器提示证书不受信任**

- 原因：自签名证书（`tools/gen_cert.py` 生成）不被浏览器信任。
- 处理：本机/可信局域网手动信任或导入证书；公网部署建议正式证书或反向代理 TLS 终止（3.4）。

**A.5.3 HTTP 局域网下 Cookie 丢失、登录态保持不住**

- 原因：`SESSION_COOKIE_SECURE` 被显式强制 `true`，纯 HTTP 下浏览器丢弃 Secure Cookie。
- 处理：改回 `unset SESSION_COOKIE_SECURE`（默认自动：纯 HTTP 局域网自动 false）或关闭显式强制；启用 HTTPS 后再设 true。

### A.6 网络与访问

**A.6.1 局域网其他设备无法访问**

- 处理：`FLASKTOOLKIT_HOST=0.0.0.0` 或 `tools/config.py set HOST 0.0.0.0`；检查系统防火墙放行端口；地址从后台"网络与访问"页复制（v4.11）。

**A.6.2 mDNS 不可用（flasktoolkit.local 无法解析）**

- 处理：`pip install zeroconf`（可选依赖）+ `python tools/config.py set MDNS_ENABLED true`（需重启）；确认局域网支持 mDNS（Windows 10+ / macOS / 多数 Linux）；跨网段不可达。

**A.6.3 本机 IP 变化后旧地址失效**

- 处理：启动横幅与后台网络页会提示新的可达地址（v4.11 IP 变化检测，`IP_WATCH_INTERVAL` 可调）；固定环境可开启 mDNS 保持 `flasktoolkit.local` 稳定可达。
