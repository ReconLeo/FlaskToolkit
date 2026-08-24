# FlaskToolkit

<p align="center">
  <img src="https://github.com/ReconLeo/FlaskToolkit/actions/workflows/ci.yml/badge.svg" alt="CI">
  <img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
  <img src="https://img.shields.io/badge/version-4.1.0-blue" alt="Version">
</p>

基于 Flask 的插件化全栈工具集。核心特性：

- **插件化**：后端插件（Python）与前端工具（HTML 包）均可动态安装/更新/卸载/启用/禁用。
- **可选鉴权**：`auth` 是可选插件——不安装时系统全员放行；安装后 API 按三层权限（游客/登录/管理员）控制。
- **热重载**：文件监听自动增量重载插件与前端工具。
- **内存注册表**：插件目录（含禁用/未加载项）缓存在内存中，首页/管理页不再每次请求扫描磁盘。

## 快速开始

```bash
pip install -r requirements.txt
python app.py
```

默认绑定 `127.0.0.1` + 自动探测可用端口（通常 5000），浏览器打开 `http://127.0.0.1:5000`。

首次运行建议安装 `plugins/auth.py` 插件以获得鉴权能力；登录默认管理员账号 `admin / admin123`（可在 `plugins/configs/auth.json` 修改）。

### 运行环境变量

| 变量 | 默认值 | 说明 |
|------|-------|------|
| `FLASKTOOLKIT_HOST` | `127.0.0.1` | 绑定地址；默认仅本机访问，如需局域网访问设 `0.0.0.0` |
| `FLASKTOOLKIT_PORT` | 自动探测 | 显式指定端口；被占用时自动回落探测可用端口 |
| `FLASKTOOLKIT_DEBUG` | 关闭 | 调试模式（`1`/`true`/`yes`/`on` 开启），开启后显示调试错误页，生产环境请勿开启 |

## 目录结构

```
FlaskToolkit/
├── app.py                     # 入口：初始化 Flask/CORS/scheduler、加载用户配置与启动自检、注册路由、关闭钩子
├── global_var.py              # 纯路径常量 + 共享状态 + 用户配置（CONFIG_ITEMS/load_user_config 覆盖）
├── requirements.txt           # 运行依赖（版本锁定）
├── requirements-dev.txt       # 开发/测试依赖
├── core/                      # 服务层（不依赖 app 实例）
│   ├── permission.py          #   统一权限体系：@permission 解析 / 三层校验 / CSRF 双提交
│   ├── plugin_loader.py       #   插件加载器：依赖校验、拓扑排序、按序加载
│   ├── plugin_cache.py        #   插件发现缓存：目录/文件指纹 + 状态快照
│   ├── plugin_pack.py         #   插件包（.zip）解析与安装
│   ├── plugin_status.py       #   插件启用/禁用状态读写
│   ├── watcher.py             #   文件监听：增量缓存 + 插件/前端工具热重载
│   ├── frontend_tools.py      #   前端工具配置加载
│   ├── stats.py               #   调用统计读写
│   ├── audit.py               #   审计日志（JSONL 追加 data/audit.log）
│   ├── package_sign.py        #   插件包完整性校验（manifest 哈希清单 + RSA 签名）
│   ├── factory_reset.py       #   工厂重置（部分/全部 scope）
│   ├── selfcheck.py           #   启动完整性自检
│   ├── logging_setup.py       #   日志配置（Flask logger + 插件日志适配器）
│   └── utils.py               #   通用工具（端口、路径参数、上传大小校验、跨插件调用等）
├── routes/                    # 路由层（按职责分组，register(app) 注入）
│   ├── interceptor.py         #   全局请求拦截器（系统级兜底鉴权）
│   ├── public.py              #   公开页面 / 错误处理器
│   ├── plugin.py              #   插件页面/API 分发
│   ├── frontend.py            #   前端工具页面 + 管理 API
│   └── admin.py               #   插件管理 API / 统计 / 日志 / 审计
├── plugins/                   # 插件目录
│   ├── base_plugin.py         #   插件基类 + @permission 装饰器
│   ├── auth.py                #   可选鉴权插件（PBKDF2 密码 / HttpOnly Cookie + CSRF）
│   └── user_manage.py         #   内置用户管理插件（BUILTIN，受 Factory Reset 保护）
├── tools/                     # 开发运维命令行工具（python tools/xxx.py）
│   ├── config.py              #   配置管理 CLI（show/set/unset/reset/check/env）
│   ├── package.py             #   插件包打包/签名/校验 CLI（genkey/pack/verify/show）
│   ├── backup.py              #   手动备份/恢复工具（Factory Reset 前备份关键数据）
│   └── reset.py               #   深度重置工具（服务停止时使用，绕过运行时文件锁定）
├── tests/                     # 回归测试套件（12 脚本 222 项 + 端到端链路验证）
├── templates/                 # 页面模板（首页/登录/错误码页 400-500/admin 管理后台/插件页）
│   ├── admin/                 #   管理后台（dashboard / plugins / logs / stats / system）
│   ├── frontend_tools/        #   前端工具模板
│   └── plugins/               #   插件页面模板
├── static/                    # 静态资源（js/plugin_common.js 统一鉴权前端、css/error.css 统一错误页样式）
├── .github/workflows/ci.yml   # GitHub Actions CI（多版本矩阵 + 全量测试 + 打包签名端到端）
├── data/                      # 运行时数据（统计/审计/用户配置，已 gitignore）
├── logs/                      # 运行日志（已 gitignore）
├── documents/                 # 框架文档（开发规范 / Roadmap / CI 上手指南）
├── LICENSE                    # MIT 许可
├── CONTRIBUTING.md            # 贡献指南
└── .gitignore                 # 运行时数据与归档文档忽略规则
```

## 权限模型

- `auth` 为**可选插件**：未安装时所有请求放行；安装后鉴权生效。
- API 权限分三层：**游客（public）/ 仅登录（user）/ 仅管理员（admin）**。
- 权限由插件通过装饰器**自行声明**（非全局路径前缀硬编码）：

```python
from .base_plugin import permission, permission as permission_required

class MyPlugin(BasePlugin):
    @permission("public")        # 游客可访问
    def login(self): ...

    @permission("user")          # 仅登录（默认）
    def info(self): ...

    @permission("admin")         # 仅管理员
    def config(self): ...
```

- 未声明任何权限的 API 默认按 `user`（仅登录）处理（安全兜底）。
- 旧版 `require_role` 装饰器兼容：其标记会被框架统一识别。

> 注意：插件类内若声明 `permission` 属性（如 `permission = "admin"`）会遮蔽装饰器，
> 请用别名导入 `from .base_plugin import permission as permission_required`。

## 插件生命周期钩子

| 钩子 | 触发时机 | 默认实现 |
|------|---------|---------|
| `on_load()` | 插件加载完成后 | 空 |
| `on_shutdown()` | 服务停止前 | 空 |
| `on_unload()` | 插件卸载前（显式卸载） | 空 |
| `on_uninstall()` | 插件删除前（显式卸载） | 空 |

## 内置插件（Builtin）

框架内置若干随系统分发、不可卸载的插件（`global_var.BUILTIN_PLUGINS`）：

| 插件 | 说明 |
|------|------|
| `auth` | 认证/会话/权限（可选插件，但作为内置分发，未安装时游客模式放行） |
| `user_manage` | 用户管理（作为内置插件，同时充当插件包机制的官方演示） |

内置插件特性：

- **受保护**：插件列表展示内置徽标；卸载接口拒绝删除内置插件；Factory Reset 的 `plugins` 范围跳过内置插件。
- **随框架分发**：内置插件的 `.py`、描述文件、模板与静态资源随项目存放，加载与其他插件一致。
- **默认账号**：`auth` 在无用户配置时自动重建默认管理员 `admin/admin123`（可被 Factory Reset 的 `builtin` 范围重置）。
- **权限模型不变**：内置插件同样通过装饰器声明三层权限（游客/登录/管理员），与普通插件一致。

## Factory Reset（重置）

将部分/全部框架数据还原至安装初始状态，接口 `POST /api/admin/factory-reset`（需管理员权限，body 带 `X-CSRF-Token`）。

请求体 `scope`：

| 值 | 重置内容 |
|------|---------|
| `"all"` | 全部（下列所有范围 + 内置配置） |
| `"plugins"` | 清除全部非内置插件（.py / 描述文件 / 模板 / 静态资源 / 临时目录），内置插件受保护 |
| `"frontend_tools"` | 清除前端工具（清单 + 模板目录） |
| `"stats_logs"` | 清除调用统计 `data/stats.json`（含内存统计）与日志 `logs/` |
| `"sessions"` | 清除登录会话 `plugins/data/sessions.json` |
| `"temp"` | 清除运行产生的临时文件（`.plugin_cache`、`__pycache__`、`temp/`、`plugins/temp/`） |

`scope` 也可传列表（如 `["sessions", "stats_logs"]`）仅重置指定范围。说明：

- `builtin` 范围仅在 `all` 时执行，重置内置插件配置（`auth` 恢复默认 `admin/admin123`）。
- 重置后自动重载插件（内置插件按默认配置重新加载）。
- 删除操作逐项容错，返回 `cleaned`/`failed` 列表（受限环境删除失败不影响接口返回）。

响应示例：

```json
{"code": 200, "data": {"cleaned": ["登录会话"], "failed": []}, "message": "重置完成"}
```

## 插件包（.zip）格式

后端插件不再以单个 `.py` 上传，而是以**插件包**（`.zip`）形式分发，类比前端的 `.zip` 工具包：包内描述文件（`plugin.json`）承载元信息，模板与静态资源随包分发。

### 包结构

```
<plugin_name>.zip
├── plugin.json          # 描述文件（必填，类比前端 config.json）
├── <plugin_name>.py     # 主插件文件（必填，文件名须与 plugin.json 的 name 一致）
├── templates/           # 可选：插件专属模板 → 解压到 templates/plugins/
└── static/              # 可选：静态资源 → 解压到 templates/plugins/static/<name>/
```

### plugin.json 字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | 是 | 插件名，须与主 `.py` 文件名一致 |
| `version` | 是 | 版本号（点分数字，支持 `v` 前缀），update 时须高于当前版本 |
| `title` | 否 | 显示名称，覆盖插件类 `title` |
| `author` | 否 | 作者，覆盖插件类 `author` |
| `category` | 否 | 分类 |
| `description` | 否 | 描述 |
| `permission` | 否 | 权限级别，覆盖插件类 `permission` |
| `dependencies` | 否 | 依赖的插件名列表 |
| `require_framework_version` | 否 | 最低框架版本要求（非强制；一经声明须满足，否则拒绝安装/加载） |

版本以 `plugin.json` 声明为准：上传/更新后描述文件落盘为 `plugins/<name>.json`，扫描与目录指纹均优先读取它。

### 最低框架版本要求（require_framework_version）

后端插件可声明 `require_framework_version`（`plugin.json` 或插件类属性，非强制）：

- **未声明**：不检查，任意框架版本可用。
- **声明了**：上传/更新时与 `global_var.FRAMEWORK_VERSION`（当前 `4.1.0`）做点分版本比较，插件要求高于框架版本则拒绝；运行时 `load_plugins` 同样校验（防止手工放置插件绕过上传校验），不满足则跳过加载。
- 比较使用 `compare_versions`（点分数字，修复了前端工具原先字符串比较的缺陷）。

参与描述一致性对齐（冲突拒绝/缺失补全）。

### 描述一致性（plugin.json 与插件类属性对齐）

`plugin.json` 与主 `.py` 内的插件类属性（name/version/title/author/permission/category/description/dependencies/require_framework_version）是**两份描述**，上传/更新时框架做对齐校验：

1. **name 三处一致**：`plugin.json.name` == 主 `.py` 文件名 == 插件类 `name`（AST 可提取时），任一不一致拒绝上传。
2. **冲突字段拒绝**：`version`/`title`/`author`/`permission`/`category`/`description`/`dependencies`/`require_framework_version` 在两处同时声明且不一致 → 拒绝并报告具体冲突字段。
3. **缺失补全**：`plugin.json` 缺失的字段回退到插件类属性（`version` 缺失用类兜底并告警）；对齐后的完整描述落盘为 `plugins/<name>.json`。

> 对齐校验通过 AST 静态解析主 `.py`（不执行插件代码）。运行时插件扫描以落盘描述文件为权威（缺失字段保留类属性兜底，兼容存量无描述文件插件）；若描述文件 `name` 与类 `name` 不一致则跳过加载并报错。

### 静态资源访问

插件页面中通过 `/plugin-static/<name>/<path>` 访问静态资源（由全局通配路由分发，热加载友好）：

```html
<link rel="stylesheet" href="/plugin-static/user_manage/css/user_manage.css">
```

### 生命周期行为

- **上传**：校验 `plugin.json` 与主 `.py` 文件名一致性 → 安全解压（内置 zip slip 防路径穿越）→ 自动加载。
- **更新**：校验包内插件名与目标一致 + 新版本必须高于当前版本 → 覆盖解压 → 重载。
- **卸载**：删除主 `.py`、描述文件、`templates/plugins/<name>.html` 与 `templates/plugins/static/<name>/` 目录。

### Demo

参考 `C:\Users\Admin\Desktop\UserManage`：`UserManage-v1.0.1.zip` 内含 `plugin.json` + `user_manage.py` + `templates/user_manage.html` + `static/css/user_manage.css`。

### 前端工具示例

框架内置前端工具示例 **随机密码生成器**（`password_generator`）：`templates/frontend_tools/password_generator.html` + `frontend_tools.json` 注册（分类：安全工具），访问 `/frontend/password_generator`。纯前端实现（密码学安全随机、强度分级、一键复制），不调用后端 API、数据不上传，可作为静态前端工具的参考模板；需要调用后端接口的前端工具按开发规范 6.2 引入 `plugin_common.js`。

前端工具 zip 包支持携带 **`static/` 静态资源目录**（CSS/JS/图片等），解压到 `templates/frontend_tools/static/<name>/`，经 `/frontend-static/<name>/<path>` 访问（安全解压 + zip slip 防护，详见开发规范 6.1/6.3）；更新时先清理旧 static 目录、卸载时一并删除。模板自动重载已开启，工具 html 更新后即时生效。

## 错误码与错误页面

框架统一错误码语义与错误页面设计（`static/css/error.css` 共享样式）。**HTTP 状态码与 body.code 一致**，前端以 `res.code` 判断业务结果：

| HTTP / code | 含义 | API 返回示例 | 页面表现 |
|------------|------|-------------|---------|
| `200` | 成功 | `{"code": 200, "message": "操作成功"}` | 正常渲染 |
| `400` | 参数错误 / 校验失败 | `{"code": 400, "message": "缺少 username"}` | 400 错误页 |
| `401` | 未登录 / 会话过期 | `{"code": 401, "message": "未登录或登录已过期"}` | 页面跳转登录页 |
| `403` | 权限不足 / CSRF 失败 | `{"code": 403, "message": "需要管理员权限"}` | 403 错误页 |
| `404` | 资源不存在 | `{"code": 404, "message": "页面不存在"}` | 404 错误页 |
| `405` | 请求方法不支持 | `{"code": 405, "message": "不支持的请求方法"}` | 405 错误页 |
| `500` | 服务器内部错误 | `{"code": 500, "message": "服务器内部错误"}` | 500 错误页 |

- 页面错误模板：`templates/400.html` `401.html` `403.html` `404.html` `405.html` `500.html`。
- API 错误响应统一走 `error_response(message, code)`，HTTP 状态码与 body.code 一致。

## 管理后台

管理后台提供前端页面管理 FlaskToolkit 应用（入口 `/admin/dashboard`，首页右上角「🛠️ 管理后台」按钮）。所有页面统一继承 `templates/admin/base.html` 布局（顶部导航 + 用户信息 + 退出登录），**受管理员权限保护**：未登录跳转登录页（携带 redirect 参数）、普通用户渲染 403 页、auth 未安装时放行。

| 页面 | 路径 | 功能 |
|------|------|------|
| 仪表盘 | `/admin/dashboard` | 统计卡片（插件/前端工具/API 调用）+ 系统信息 + 快捷入口 + 内置插件列表 |
| 插件管理 | `/admin/plugins` | 上传 / 更新 / 卸载 / 启用 / 禁用 / 配置 / 全部重置 |
| 日志 | `/admin/logs` | 按级别（debug/info/warning/error/critical）与行数查看日志，支持按插件过滤 |
| 统计 | `/admin/stats` | API 调用 Top100（可搜索）+ 前端工具访问 Top100 |
| 系统管理 | `/admin/system` | 系统信息 + Factory Reset（分 scope 勾选 / 全部重置，见上文） |

配套管理端接口（均在 `/api/admin/*`，默认强制管理员权限）：

- `GET /api/admin/system/info`：框架版本、内置插件列表、Python/平台版本、base_dir、host、debug 标志及各类统计数。
- `GET /api/admin/stats`：插件数（含 catalog）、前端工具数、API 调用与前端访问统计明细。
- `GET /api/admin/logs`：按 `level`/`lines`/`plugin` 读取日志；级别映射到 `app.log`（INFO+）与 `error.log`（ERROR+），warning/critical 按行内 ` - LEVEL - ` 标记二次过滤。

## 测试

回归测试套件位于项目 `tests/` 目录（项目根路径自动推导，可在任意位置运行，不污染项目文件）：

```bash
cd FlaskToolkit
python tests/test_permission.py       # 权限体系 20 项
python tests/test_stage2.py           # 安全加固回归 19 项
python tests/test_zip_slip.py         # 插件包 zip slip 专项 19 项
python tests/test_pack_meta.py        # 插件包描述一致性 17 项
python tests/test_reload_race.py      # 热加载重载竞态回归（test client，20 轮）
python tests/test_meta_e2e.py         # 插件包元信息端到端 10 项（隔离目录模式）
python tests/test_frontend_zip_slip.py# 前端工具 zip slip 专项 21 项
python tests/test_frontend_chain.py   # 前端工具链路端到端 23 项（隔离目录）
python tests/test_admin_api.py        # 管理端 API 21 项（隔离目录）
python tests/test_factory_reset.py    # Factory Reset 范围 37 项（隔离目录）
python tests/test_error_pages.py      # 错误码页面渲染 12 项（隔离目录）
python tests/test_package_sign.py     # 完整性校验/签名专项 22 项（隔离目录）
# 合计 12 个脚本 222 项
```

## 开发运维工具

```bash
# 配置管理（路径/选项/运行参数持久化到 data/user_config.json）
python tools/config.py show                        # 查看所有可配置项
python tools/config.py set HOST 0.0.0.0            # 设置（含 FLASKTOOLKIT_HOST/PORT/DEBUG）
python tools/config.py set PACKAGE_INTEGRITY_MODE strict
python tools/config.py env                         # 生成环境变量示例

# 插件包打包/签名/校验（完整性校验，方案C）
python tools/package.py genkey -o private.pem --pub public.pem
python tools/package.py pack ./demo_tool -o demo_tool.zip --type frontend --sign private.pem --signer "张三"
python tools/package.py verify demo_tool.zip --public-key public.pem

# 手动备份/恢复（Factory Reset 前备份关键数据）
python tools/backup.py create                # 创建备份
python tools/backup.py list                  # 列出备份
python tools/backup.py restore <名称>        # 恢复备份

# 深度重置（服务停止时使用，绕过运行时文件锁定）
python tools/reset.py list                   # 列出可重置范围
python tools/reset.py reset all --auto-backup # 先备份再全部重置

# 框架完整性自检（每次启动自动执行，也可手动）
python core/selfcheck.py
```

## 开源与 CI

本项目已为 GitHub 开源与持续集成做好准备：

- **CI 工作流**：[`.github/workflows/ci.yml`](.github/workflows/ci.yml) —— push / PR 时在 Python 3.10/3.11/3.12 上自动运行完整回归测试（`tests/`，222 项）+ 框架完整性自检 + 打包/签名工具端到端。
- **开源配套**：`LICENSE`（MIT）、`CONTRIBUTING.md`（贡献指南）、`.gitignore`（排除运行时数据）。
- **操作指导**：首次接触 GitHub Actions？从发布到贡献的完整步骤见 [GitHub Actions 上手与开源发布指南](documents/GitHub-Actions-上手与开源发布指南.md)。

## 人工智能辅助开发声明

本项目在开发过程中使用了 AI 辅助编程工具，包括但不限于：代码生成与重构、代码审查、测试用例编写、文档撰写。所有由 AI 辅助生成或修改的内容，均已由开发者进行人工审查，并通过项目自身的回归测试套件（`tests/`，222 项）与启动完整性自检验证后才会合入。

对贡献者的透明性约定：

- 使用 AI 辅助工具（如 GitHub Copilot、各类 AI 编程助手等）是被允许的，但请对提交代码的**正确性、安全性、合规性**负全责。
- AI 生成的代码必须通过项目的回归测试与代码审查（流程见 `CONTRIBUTING.md`）。
- 若 PR 中大量使用 AI 生成内容，建议在 PR 描述中注明，便于维护者审阅。
