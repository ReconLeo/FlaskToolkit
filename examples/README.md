# FlaskToolkit 官方示例

本目录提供一套**随仓库分发、可一键安装**的示例插件/工具包，用于完整展示框架的各类能力，也是新插件开发的起始模板。

## 示例总览

| 示例 | 类型 | 安装后访问 | 展示的框架能力 |
|------|------|-----------|---------------|
| `hello_plugin`（Hello 脚手架） | 后端插件 | `/plugin/hello_plugin` | 生命周期钩子（on_load/on_shutdown/on_unload/on_uninstall）、三层权限路由（public/user/admin）、配置读写、自定义页面 |
| `scheduler_demo`（APScheduler 定时任务） | 后端插件 | `/plugin/scheduler_demo` | `scheduled_tasks` 属性声明定时任务、interval 与 cron 双触发器、定时数据持久化、页面实时展示调度历史 |
| `async_file_demo`（异步任务与文件上传） | 后端插件 | `/plugin/async_file_demo` | 上传类型/大小限制、`save_uploaded_file`、`run_async_task` 异步处理、状态轮询、`send_file_response` 下载结果 |
| `dependent_demo`（插件依赖与跨插件调用） | 后端插件 | `/plugin/dependent_demo` | `dependencies` 依赖声明（缺失依赖拒绝加载）、`call_plugin_method` 跨插件调用 auth |
| `dashboard_demo`（Dashboard 管理面板） | 前端工具包 | `/frontend/dashboard_demo` | admin 权限前端工具、调用后端 admin API、ECharts 图表、zip 静态资源上传与访问 |

## 快速开始

前置：启动服务并确认管理员账号（默认 `admin / admin123`），安装 `requests`：

```bash
pip install -r requirements.txt -r requirements-dev.txt
python app.py                      # 启动服务（另开一个终端）
```

一键安装全部示例（登录 → CSRF → 正式 API 上传，含溯源/审计）：

```bash
python examples/install_all.py     # 默认连接 http://127.0.0.1:5000，账号 admin/admin123
```

仅打包（不依赖服务，生成 `examples/dist/*.zip`，可手动在管理后台上传）：

```bash
python examples/install_all.py --pack-only
```

一键卸载全部示例：

```bash
python examples/install_all.py --uninstall
```

自定义服务地址/账号：

```bash
python examples/install_all.py --base-url http://127.0.0.1:5000 --username admin --password 你的密码
```

## 各示例详解

### 1. hello_plugin —— 插件开发的起始模板

复制 `plugins/hello_plugin/` 目录改造成你自己的插件。关键点：

```python
class HelloPlugin(BasePlugin):
    name = "hello_plugin"
    permission = "user"              # 插件级默认权限

    def on_load(self): ...           # 加载完成后初始化（加载配置等）
    def on_shutdown(self): ...       # 服务停止前清理

    @property
    def routes(self):                # 声明路由（含参数描述，自动生成 API 文档）
        return [{"path": "/admin", "name": "...", "methods": ["GET"],
                 "view_func": self.api_admin, ...}]

    @permission("admin")             # 路由级权限：public/user/admin
    def api_admin(self): ...
```

### 2. scheduler_demo —— 定时任务（APScheduler）

通过 `scheduled_tasks` 属性声明，框架加载时自动注册到 APScheduler：

```python
@property
def scheduled_tasks(self):
    return [
        {"func": self.interval_heartbeat, "trigger": "interval", "seconds": 30},
        {"func": self.cron_summary, "trigger": "cron", "minute": "*"},
    ]
```

每个任务配置传给 `scheduler.add_job(func=..., id=..., **task_config)`，`trigger` 支持 `interval` / `cron` / `date`，其余参数与 APScheduler 一致（如 `max_instances`、`hour` 等）。

### 3. async_file_demo —— 异步任务与文件上传

长耗时任务不阻塞请求：上传后立即返回 `task_id`，后台线程处理，前端轮询状态，完成后下载结果。

```python
# 上传限制（save_uploaded_file 自动校验类型；超大小返回 413）
@property
def allowed_upload_types(self): return ['.txt', '.log', '.csv', '.json', '.md']

temp_path, original_name = self.save_uploaded_file("file")
task_id = self.run_async_task(self._process_file, temp_path, original_name)
status  = self.get_async_task_status(task_id)      # running/success/failed
return self.send_file_response(result_file, download_name=..., mimetype="application/json")
```

### 4. dependent_demo —— 插件依赖与跨插件调用

```python
class DependentDemoPlugin(BasePlugin):
    dependencies = ["auth"]          # 依赖声明：加载器拓扑排序，缺失则拒绝加载

    def get_users(self):
        users = self.call_plugin_method("auth", "get_all_users")  # 跨插件调用
```

安装时若 auth 未安装，该插件会被拒绝安装——这正是依赖机制的演示。

### 5. dashboard_demo —— 前端工具包完整形态

区别于纯前端工具（如内置的密码生成器），本示例展示：

- `config.json` 声明 `permission: "admin"`；
- 页面调用受 `@admin_api` 保护的后端接口（`/api/admin/system/info`、`/api/admin/stats`），未登录/非管理员会被 `plugin_common.js` 拦截跳转；
- 携带 `static/` 静态资源（css/js），经 `/frontend-static/<name>/` 提供；
- ECharts 图表（示例用 CDN，生产可下载到 `static/` 本地化）。

## 目录结构

```
examples/
├── README.md                  # 本说明
├── manifest.json              # 示例清单（install_all.py 读取）
├── install_all.py             # 一键打包/安装/卸载
├── plugins/                   # 后端插件示例（源目录 = 插件包结构）
│   ├── hello_plugin/          #   plugin.json + <name>.py + templates/
│   ├── scheduler_demo/
│   ├── async_file_demo/
│   └── dependent_demo/
└── frontend_tools/            # 前端工具包示例
    └── dashboard_demo/        #   config.json + <name>.html + static/
```

## 注意事项

- 示例安装会写入真实项目运行时目录（`plugins/`、`templates/`、`frontend_tools.json`），卸载后清理。若要测试隔离环境，请使用临时副本或先备份。
- `dependent_demo` 依赖 `auth` 插件；`scheduler_demo` 的心跳数据持久化在 `data/scheduler_demo.json`，重启服务后保留。
- 想自己打包插件？直接复制某个示例目录，修改 `plugin.json` 与主文件后，用 `python tools/package.py pack <目录> -o xxx.zip --type backend|frontend` 打包（支持 `--sign` 签名）。
