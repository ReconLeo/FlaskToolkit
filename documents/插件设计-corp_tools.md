# corp_tools 插件设计：企业内网工具箱

> 设计目标：面向**企业内网生产环境**提供一个真实可用的综合插件，同时**系统性展示 FlaskToolkit 框架能力**，作为官方示例的"压轴"参考模板。
> 状态：设计稿 v1（2026-09-03）→ 实现

## 一、场景定位

企业内网（可信局域网）的日常运维/协作需求：

1. **服务健康检查**：内网各业务服务（ERP、OA、GitLab、Jenkins…）是否在线、响应时延如何——运维日常刚需；
2. **内部工具导航**：把散落的内网系统/工具链接收拢成一站式导航页（按部门/权限可见性分组）；
3. **公告板**：IT/行政发布停机维护、版本发布、制度通知等公告，员工登录可见。

这三个功能合并为一个插件 `corp_tools`，贴合"内网生产环境"的真实使用场景。

## 二、框架能力展示清单（设计显式覆盖）

| 框架能力 | 在 corp_tools 中的落点 |
|---------|----------------------|
| 插件包结构（plugin.json + 多 .py + templates + static） | 标准插件包：`corp_tools.py` 主文件 + `corp_utils.py` 辅助模块 + 3 个模板 + 1 个 css/js |
| capabilities 声明（10.7） | `scheduler`（健康检查定时任务）+ `network:http`（内网服务探测，白名单/防火墙语义）|
| 定时任务（scheduled_tasks） | 每 60s 后台探测一次服务健康状态并缓存 |
| 数据目录（get_data_path，隐式豁免） | 健康状态缓存、公告数据存 `plugins/data/corp_tools/` |
| 配置读写（load_config/save_config） | 服务清单、导航链接、公告管理走配置持久化 |
| 三层权限（public/user/admin） | 健康页 public（登录可见）/ 导航 admin 维护 / 公告 admin 发布、user 查看 |
| 多模板页面路由（page=True） | 主入口 index.html + 子页 health.html（健康）/ links.html（导航）/ notices.html（公告） |
| 静态资源（/plugin-static/） | corp.css + corp.js（页面刷新健康状态） |
| 异步任务（run_async_task） | 公告发布时异步写入 + 探测耗时任务异步化（展示不阻塞请求） |
| 跨插件调用（call_plugin_method） | 可选：调用 auth 获取当前用户角色显示"欢迎 xx" |

## 三、功能与接口设计

### 3.1 服务健康检查（health）

- 配置：`services` 列表（`{name, url, group}`，示例预置 3 个内网地址，可在管理后台增删）。
- 定时任务：每 60 秒对所有服务发起 HTTP HEAD/GET 探测（超时 3s），记录 `{up, status_code, latency_ms, checked_at}` 到缓存文件。
- API：
  - `GET /api/corp_tools/health`（public）→ 返回缓存的服务健康状态。
- 页面：`/plugin/corp_tools/health` 子页，前端 JS 轮询 health API，红/绿状态卡片展示。

### 3.2 内部工具导航（links）

- 配置：`links` 列表（`{name, url, group, permission}`，permission ∈ public/user/admin）。
- 页面：`/plugin/corp_tools/links` 子页，按当前用户权限过滤可见链接，按分组展示。
- API：
  - `GET /api/corp_tools/links`（public，按权限过滤）→ 返回可见链接列表。
  - `POST /api/corp_tools/links`（admin）→ 新增链接（写配置）。

### 3.3 公告板（notices）

- 数据：`plugins/data/corp_tools/notices.json`（get_data_path）。
- API：
  - `GET /api/corp_tools/notices`（user）→ 公告列表（倒序）。
  - `POST /api/corp_tools/notices`（admin）→ 发布公告（`{title, content, level}`，异步落盘）。
  - `DELETE /api/corp_tools/notices/<id>`（admin）→ 删除公告。
- 页面：`/plugin/corp_tools/notices` 子页（展示 + 发布表单）。

### 3.4 主入口 index

- `/plugin/corp_tools`：三卡片导航（健康 / 导航 / 公告）+ 当前用户欢迎语（跨插件调 auth）。

## 四、plugin.json 设计

```json
{
  "name": "corp_tools",
  "title": "示例：企业内网工具箱",
  "version": "1.0.0",
  "author": "FlaskToolkit Examples",
  "category": "示例",
  "description": "企业内网综合示例：服务健康检查（定时探测+网络白名单 capabilities）+ 内部工具导航（权限过滤）+ 公告板（异步落盘），系统性展示框架多模板/权限/定时任务/配置读写/数据目录/静态资源能力。",
  "permission": "user",
  "require_framework_version": "4.3.2",
  "capabilities": [
    "scheduler",
    "network:http:http://127.0.0.1:5000/*",
    "network:http:http://127.0.0.1:8080/*",
    "network:http:http://127.0.0.1:9000/*",
    "network:http:http://*.intra.corp/*"
  ]
}
```

> 说明：`network:http:http://127.0.0.1:5000/8080/9000/*` 精确端口声明覆盖示例预置的本机探测地址（端口通配 `:*` 不被支持，必须精确数字）；`network:http:http://*.intra.corp/*` 演示子域通配（框架允许 `*.dom` 子域通配，**禁裸 `*`**）。实际企业部署按真实内网主机收敛。

## 五、目录结构

```
examples/plugins/corp_tools/
├── plugin.json
├── corp_tools.py          # 插件主类（routes/定时任务/API）
├── corp_utils.py          # 辅助模块（纯函数：探测封装/链接过滤/公告排序）
├── templates/
│   ├── corp_tools.html    # 主入口 index（render_index）
│   ├── corp_tools_health.html
│   ├── corp_tools_links.html
│   └── corp_tools_notices.html
└── static/
    ├── css/corp.css
    └── js/corp.js
```

## 六、验收标准

1. `examples/install_all.py --pack-only` 打包通过；
2. 上传安装成功（report 模式），capabilities 摘要无 `missing`；
3. 页面 `/plugin/corp_tools` + 3 子页 200；
4. health API 返回服务状态（含定时任务写入的缓存）；
5. links 按权限过滤（admin 可见 admin 链接）；
6. notices 发布/列表/删除闭环（admin 发布 → user 可见）；
7. 框架全量回归 22 脚本仍全通过（新增插件不影响既有测试）。

## 七、与既有示例的差异化定位

| 示例 | 侧重 | corp_tools 补充 |
|------|------|----------------|
| hello_plugin | 最小脚手架 | 综合多功能插件结构 |
| scheduler_demo | 定时任务单点 | 定时任务+网络探测联动 |
| async_file_demo | 文件/异步单点 | 异步落盘+多 API 协作 |
| multitool_demo | 大插件三要素 | 大插件+capabilities+权限过滤 |
| corp_tools | **企业内网综合场景** | 以上能力**系统性组合** + capabilities 网络白名单 + 权限过滤导航 + 公告板 |
