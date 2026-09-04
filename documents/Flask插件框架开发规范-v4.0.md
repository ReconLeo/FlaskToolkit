# Flask插件框架开发规范

## 版本：v4.7.0（装饰性更新：项目宣传与系统名个性化） | 更新日期：2026年09月04日

### 版本说明（v4.7.0 变更：装饰性更新 F2/F3）
- **框架版本升级至 v4.7.0**，本次为装饰性更新（不影响插件 API 与内部逻辑）：
  1. **项目宣传（F2）**：`global_var.py` 新增只读常量 `PROJECT_NAME` / `PROJECT_AUTHOR` / `PROJECT_GITHUB` / `PROJECT_SLOGAN`（不进 `CONFIG_ITEMS`）；`app.py` 启动时打印项目横幅（系统名称 + 版本标签 + 标语 + 框架版本 + 作者 + GitHub 链接）；管理后台页眉新增 GitHub 链接；`/api/admin/system/info` 返回 `system_name` / `system_version` / `project_*` 字段；系统管理页新增"关于项目"卡片。
  2. **系统名个性化（F3）**：新增 `CONFIG_ITEMS` 配置项 `SYSTEM_NAME`（默认 FlaskToolkit）与 `SYSTEM_VERSION_LABEL`（默认 v4.7.0，仅装饰展示，不改 `FRAMEWORK_VERSION` 逻辑，升级框架时建议同步更新）；`app.py` 注册模块级 Jinja context processor，向所有页面注入 `system_name` / `system_version` / `project_github` / `project_name` / `project_author` / `project_slogan`（内部动态读取用户配置，测试环境直接导入 app 亦生效）；登录页 / 首页 / 管理后台 / 插件默认页 / 7 个错误码页面将硬编码系统名替换为 `{{ system_name }}`；footer 仅完成注入准备、不新增布局。
- **版本边界**：`SYSTEM_VERSION_LABEL` 只影响前端展示，`FRAMEWORK_VERSION` 仍为插件 `require_framework_version` 比较基准；自定义 `SYSTEM_NAME` 不改内部插件名/路由标识。
- **回归测试 22 脚本 500 项全部通过**（F2/F3 为纯展示层变更，未新增断言）。

## 版本：v4.6.0（审计钩子归因修复） | 更新日期：2026年09月04日

### 版本说明（v4.6.0 变更：审计钩子归因修复 + 严格模式验证）
- **框架版本升级至 v4.6.0**：严格模式（`PLUGIN_SCAN_MODE=enforce` + `AUDIT_HOOK_MODE=enforce` + `PACKAGE_INTEGRITY_MODE=strict` 预设）系统验证中修复 `core/audit_hook.py` 插件归因两处缺陷：
  1. **enforce 下任何插件无法加载（阻断级）**：框架自身扫描/加载插件时（`scan_plugin_metadata` / `load_plugins` 经 `importlib.import_module` 导入），模块顶层 `from plugins.base_plugin import ...` 触发 `open(plugins/base_plugin.py)`，`_locate_plugin()` 沿调用栈把发起者误归因为被导入插件 → 未声明 `filesystem:read` 拒绝安装/加载。修复：调用栈中出现框架加载器帧（`core/plugin_cache.py` / `core/plugin_loader.py`）即视为框架行为放行。
  2. **插件包辅助模块误归因**：`corp_utils.py` 等非 `BasePlugin` 子类的辅助模块被归因为独立插件名，导致主插件自属路径（`plugins/data/<name>/`、`plugins/configs/<name>.json`）隐式豁免失效，enforce 下异步落盘/数据目录读写被误拦。修复：优先归因“定义了 `BasePlugin` 子类”的最近帧，辅助模块帧跳过；全栈无插件类时回退最近帧。
- **回归测试扩充至 22 脚本 499 项**：`test_audit_hook.py` B 组新增 B4（框架加载器帧放行）/ B5（辅助模块归因主插件，含 sys.modules 污染防护——B5 用桩基类避免污染 E 组隔离环境）。
- **严格模式验证（D1-D8）**：预设可应用性与持久化、冷启动自检、上传链路（恶意拒绝/良性放行/未声明网络拒绝/zip slip）、运行时（corp_tools 定时探测/异步落盘/越权拦截）、登录会话（3 次锁定/解封/secure cookie/空闲超时）、管理后台、全量回归（strict 下 22 脚本全过）、资源稳定性（30 轮探测/审计统计/路径过滤）全部通过；验证结论：strict 预设可直接用于可信局域网/企业内网，配套 HTTPS 使用。

### 版本说明（v4.5.1 变更：登录锁定手动解封）
- **框架版本升级至 v4.5.1**：审计意见落地——登录失败锁定后，后台应可手动解封。auth 插件新增 `unlock_user(username)`（清除该用户名全部维度锁定记录，兼容 `LOGIN_LOCK_MODE` 的 username / ip_username 双维度）与 `is_user_locked(username)`（锁定状态查询）；user_manage 插件新增 `POST /api/user_manage/unlock` 接口（admin 权限）并在用户列表返回 `locked` 状态字段，前端表格新增"状态"列（正常/已锁定）与**解封**按钮（仅锁定用户显示）。
- **解封语义**：无需等待锁定期满即可立即恢复登录；解封不存在的用户返回 404，解封无锁定记录用户返回 200 并提示"当前无锁定记录"（幂等）。
- **回归测试扩充至 22 脚本 497 项**：test_security.py 新增 H 段（auth 方法层 6 项：ip_username/username 双维度锁定识别与解封、解封后恢复登录、未锁定用户幂等）与 I 段（user_manage 端点层 9 项：未登录 401、管理员登录后解封 200、解封后可登录、不存在用户 404、未锁定用户提示无记录）。

### 版本说明（v4.5.0 变更，收尾：HTTPS 支持 + 路径迁移 + 检修）
- **框架版本升级至 v4.5.0**：在 4.4.0 安全强化收官后的收尾版本——补齐部署形态（HTTPS）、归位运行时数据路径（frontend_tools.json / auth 会话），并对既有检修文件（selfcheck / factory_reset / tools / 示例插件）做一致性体检。
- **可选 HTTPS（默认 HTTP）**：新增 `SSL_CERT_FILE` / `SSL_KEY_FILE` 配置项（`kind=path`），两者均配置且文件存在时 `app.run(ssl_context=(cert, key))` 以 HTTPS 启动并打印 `https://` 地址；只配一项或文件缺失回退 HTTP 并告警。配套 `tools/gen_cert.py` 用系统 openssl 一键生成自签名证书/私钥（RSA 2048、SAN 含 localhost/127.0.0.1 可 `--san` 追加局域网 IP/DNS，输出 `data/certs/`，`.gitignore` 已忽略私钥）。
- **frontend_tools.json 默认路径迁移至 `data/`**：`FRONTEND_CONFIG_FILE` 默认值改为 `data/frontend_tools.json`（`core/frontend_tools.py` 同步改用常量并新增 `LEGACY_CONFIG_FILE` + `migrate_legacy_config()`——根目录旧文件在 `data/` 无文件时 os.replace 原子迁移，两处并存时告警保留新路径）；`tools/backup.py` BACKUP_ITEMS、`core/selfcheck.py` 相应更新。
- **auth 会话文件迁移至插件自属目录**：`_get_session_file_path` 由 `plugins/data/sessions.json` 改为 `self.get_data_path("sessions.json")`（`plugins/data/auth/`，纳入 capabilities 隐式豁免，enforce 模式下不再崩溃）；旧文件在加载时自动 os.replace 迁移；`core/factory_reset.reset_sessions`、`tools/backup`、`tests/ci_cleanup` 等同步新路径并兼容清理旧文件。
- **示例插件数据路径归位**：`async_file_demo` 结果目录由 `data/async_file_demo` 改为 `self.get_data_path('results')`（插件自属目录，enforce 安全）；`hello_plugin` / `scheduler_demo` / `multitool_demo` / `dependent_demo` 已确认使用自属路径或无文件操作；`user_manage` 无自有文件读写（全部经 auth 插件 API）。
- **审计钩子框架路径过滤**：`core/audit_hook.py` 新增 `_is_framework_path()`——logs/data/backups/temp 属框架管理目录（插件经框架 logger/stats 写入非插件业务），不归因拦截（此前 enforce 模式下插件写日志会触发崩溃）；解释器路径过滤保持原有逻辑。
- **selfcheck CORE_FILES 补全**：纳入 v4.3.x-v4.4.0 新增模块（plugin_scanner / capabilities / audit_hook / plugin_cache / plugin_status / routes/security.py）；`frontend_tools.json` 属运行时配置（不入库、缺失不致命），从致命清单移除由迁移逻辑初始化。
- **回归测试 22 脚本 482 项全量通过**（新增/调整用例覆盖会话路径迁移、frontend_tools 迁移与备份条目、框架路径过滤等），已纳入 CI。

### 版本说明（v4.4.0 变更，安全强化 P1 阶段三：运行时审计钩子）
- **框架版本升级至 v4.4.0**：安全强化 P1 收官。基于 CPython 原生 `sys.addaudithook` 建立运行时防线，与 4.3.1 静态扫描（安装时事实）、4.3.2 capabilities 声明（安装时授权比对）构成纵深防御第三层——"安装时静态审查 → 安装时授权比对 → **运行时兜底**"。
- **运行时审计钩子（`core/audit_hook.py`，新增 10.8）**：监听敏感操作事件（open 读写/删除族/mkdir、os.system/subprocess.Popen、socket.connect/bind、sqlite3.connect），**调用栈遍历定位 plugins/<name>.py 帧**归属插件（base_plugin 等框架内置帧排除、解释器内部路径过滤），按 4.3.2 注册的 capabilities 授权判定（网络白名单即"防火墙"）。
- **AUDIT_HOOK_MODE 三档**：`off` 不安装（零开销）/ `observe`（默认）聚合计数+审计落盘不阻断 / `enforce` 未授权行为抛 RuntimeError 阻断（插件可捕获）；config CLI 可调，profile 三预设联动（daily→observe / strict→enforce / lan-open→off）。
- **未授权行为按插件聚合**（审计意见落地）：`core/audit_hook._VIOLATIONS` 内存聚合（plugin→capability→count+事件样本），`/api/admin/stats` 新增 `audit_violations` 按插件分组返回，**合计由前端完成**；管理后台统计页新增红色统计卡与明细表，**建议声明可点击复制**（`suggest_for_action` 与安装期交叉校验共用生成器，作者可明确看到"哪个插件、缺哪条声明、干了什么"）。
- **实现约束**：hook 内零 IO（递归防护 threading.local）；审计写入走内存待落盘队列 + 后台线程（`flush_now()` 同步落盘）；插件重载/卸载时聚合清零。
- **顺带修复框架既有 bug**：`core/audit.py current_actor()` 在无请求上下文（后台线程）时 werkzeug LocalProxy 抛 RuntimeError 崩溃——getattr 访问移入 try（此前 scheduler 后台任务写审计日志也会触发）。
- **回归测试扩充至 22 脚本 482 项**：新增 `test_audit_hook.py`（36 项：事件映射 9 / 栈定位 3 / observe 聚合 7 / enforce 阻断 5 / 隔离集成 12），已纳入 CI。
- **P1 安全强化至此全部完成**（P0 4.3.0 + P1 阶段一 4.3.1 + 阶段二 4.3.2 + 阶段三 4.4.0）；权限模型细化（超级管理员/普通管理员）与进程级沙箱列为远期规划。

### 版本说明（v4.3.2 变更，安全强化 P1 阶段二：插件能力声明模型）
- **框架版本升级至 v4.3.2**：继 4.3.1 静态扫描（事实提取）之后，本阶段引入插件**能力白名单声明**（授权声明），安装时交叉校验，构建"安装时静态审查 → 安装时授权比对 → 运行时兜底"纵深防御的中间层。
- **能力声明模型（`core/capabilities.py`，新增 10.7）**：plugin.json 可选 `capabilities` 字段，扁平字符串列表语法（`域:子域:参数`），8 大域能力目录——filesystem（read/write 路径前缀）、network（http/tcp/udp/server，host 精确或 `*.dom` 子域通配，禁裸 `*`）、webhook（wecom/dingtalk/feishu + URL 白名单）、process（exec[.bin]）、scheduler、database（sqlite/mysql/postgres）、device（serial/print）、env（read 变量名模式）；未知域安装告警不拒绝（开放集合，向后兼容）。
- **安装链路交叉校验**：`_scan_gate` 扩展——扫描器范围输出（paths_read/paths_written/network_endpoints/findings）× 声明白名单 → `missing`（未声明）/`implicit_granted`（隐式豁免）/`unused`（声明未用，info）/`suggested`（**建议声明自动生成**，可整段复制回 plugin.json）；`PLUGIN_SCAN_MODE=enforce` 下高风险 **或** missing 非空即拒绝（400 附完整清单），report 放行附摘要；上传/更新响应新增 `capabilities` 字段。
- **自属路径隐式豁免（implicit grants）**：插件自己的 `plugins/configs/<name>.json`、`plugins/data/<name>/**`、`plugins/temp/<name>/**` 无需声明即可读写（基类配置 API 与拼接写法的扫描盲区由运行时层兜底）；跨插件目录与 `data/`（框架自身数据）不豁免。
- **插件数据目录框架化（base_plugin）**：新增 `data_dir` 属性（`plugins/data/<name>/`，自动创建）与 `get_data_path(*sub)` 助手。
- **运行时授权 API（阶段三契约）**：`register_capabilities`/`check_filesystem`/`check_network`/`check_process`——loader 加载插件时从描述文件注册能力集，作为 4.4.0 运行时审计钩子的授权判定依据（网络白名单即"防火墙"规则）。
- **官方示例**：全部补 capabilities 声明（scheduler_demo 演示 `scheduler` + 心跳迁移 `get_data_path`；hello_plugin 新增 `/data-demo` 接口演示数据目录隐式豁免）。
- **回归测试扩充至 21 脚本 447 项**：新增 `test_capabilities.py`（51 项：解析 6 / 匹配语义 10 / 交叉校验 12 / 运行时 API 7 / 安装链路集成 10 / base_plugin data API 6），已纳入 CI。
- **后续计划（P1 阶段三，4.4.0）**：`sys.addaudithook` 运行时审计钩子 + `AUDIT_HOOK_MODE` 三档（off/observe/enforce 按 capabilities 与网络白名单阻断）。

### 版本说明（v4.3.1 变更，安全强化 P1 阶段一：插件静态扫描 + 配置预设）
- **框架版本升级至 v4.3.1**：内部安全加固第二阶段（P1 阶段一），新增插件安装链路静态扫描门禁与安全配置预设，并整合审计建议（配置预设 / 读写范围声明 / 网络防火墙）的第一步落地。
- **插件静态扫描器（`core/plugin_scanner.py`，新增 10.6）**：基于 AST 的后端插件/插件包扫描 + 正则级前端 HTML 扫描——危险导入（subprocess/pickle/ctypes 等 high；socket/requests 等 medium）、危险调用（os.system/eval/exec/rmtree/pickle.loads 等）、动态导入与混淆（base64+exec、`__import__` 拼接）、socket 服务端（bind/listen 视为 high）、`import as` 与实例别名归因（`s = socket.socket(); s.connect(...)`）；**范围提取** `paths_read` / `paths_written` / `network_endpoints`，作为 P1 阶段二 capabilities 声明交叉校验的基准。
- **安装链路门禁（`PLUGIN_SCAN_MODE` 三档）**：`off` 跳过 / `report`（默认）放行并在响应附 `scan` 摘要与 `scan_scope`、审计日志记录 / `enforce` 检出高风险即拒绝安装（400 附完整 `scan_report`、审计日志记录 blocked）；后端插件上传/更新（admin）与前端工具上传/更新（frontend）四端点全部接入。
- **扫描 CLI（`tools/scan.py`）**：支持单文件 .py、插件包/前端工具包 .zip（config.json 自动识别）、目录批量递归，`--json` 机器可读输出；退出码 0 无高风险 / 1 有高风险 / 2 错误，供发布者分发前自检。
- **安全配置预设（`tools/config.py profile`）**：内置 `daily`（日常基线）/ `strict`（运维加固，需 HTTPS）/ `lan-open`（可信局域网开放）三套预设，一键套用后仍可 `set` 单项微调。
- **回归测试扩充至 20 脚本 396 项**：新增 `test_plugin_scan.py`（35 项：扫描器单元 15 / 插件包 2 / 前端扫描 5 / enforce 门禁集成 7 / 配置预设 6），已纳入 CI。
- **后续计划（P1 阶段二/三）**：插件 capabilities 声明模型（读写路径 / 网络端点，与扫描范围交叉校验）、运行时审计钩子（网络白名单"防火墙"式阻断）；权限模型细化（超级管理员 / 普通管理员）列为远期规划。

### 版本说明（v4.3.0 变更，系统安全强化）
- **框架版本升级至 v4.3.0**（`global_var.FRAMEWORK_VERSION`）：外部（局域网环境）与内部（插件恶意代码）双重安全加固的第一阶段（P0），全部项可经 config CLI 调整。
- **统一安全响应头（10.2）**：所有响应注入 5 项安全头——`X-Content-Type-Options: nosniff` / `X-Frame-Options: DENY` / `Content-Security-Policy`（默认"宽"策略允许 inline script/style 兼容存量插件，P1 静态扫描就绪后收紧）/ `Referrer-Policy: no-referrer` / `Permissions-Policy`（禁用摄像头/麦克风/定位）；同时移除 `Server` / `X-Powered-By` 隐藏框架指纹。由 `SECURITY_HEADERS` 开关控制（默认开启）。
- **会话 Cookie 加固（6.2 / auth）**：登录会话 token 与 CSRF token Cookie 均携带 `HttpOnly`（token）+ `SameSite=Lax`；新增 `SESSION_COOKIE_SECURE`（默认 False，兼容 HTTP 局域网部署；HTTPS 部署置 True 后 Cookie 带 `Secure` 属性，防中间人窃取）。
- **会话空闲超时（auth）**：新增 `SESSION_IDLE_TIMEOUT`（默认 30 分钟）：会话在最后活动时间后超过阈值即失效（`verify_token` 校验并在有效请求时刷新 `last_active_at`，仅内存不落盘）。
- **登录失败锁定（auth）**：新增 `LOGIN_LOCK_MODE` 三档开关——`ip_username`（默认，IP+用户名双维度，防分布式爆破）/ `username`（仅用户名维度）/ `off`（禁用锁定，不安全，仅信任局域网时使用）；阈值 `LOGIN_MAX_ATTEMPTS`（默认 5 次）与锁定时长 `LOGIN_LOCK_SECONDS`（默认 15 分钟）可配置；锁定期间统一返回 **429 通用错误信息**（不泄露锁定剩余时间等细节）；登录成功后自动清除失败计数。
- **回归测试扩充至 19 脚本 361 项**：新增 `test_security.py`（30 项：安全响应头 8 项 / Cookie 加固 6 项 / 空闲超时 5 项 / 登录锁定 ip_username 6 项 / username 2 项 / off 2 项 / 成功重置 1 项），已纳入 CI。
- **后续计划（P1）**：静态扫描工具已随 v4.3.1 落地（见上文）；运行时审计钩子、插件 capabilities 声明模型列为后续版本；权限模型细化（超级管理员 / 普通管理员仅管理特定功能）列为远期规划。

### 版本补充说明（2026-08-26，AirDrop 插件化改造同步）
- **插件公开页面能力（8.1 / 4.5.1）**：`/plugin/<name>` 页面默认要求登录（全局守卫）。新增插件级豁免：插件实例声明 `public_page=True` 时其 `/plugin/` 页面免登录（对局域网公开工具 / 信息落地页友好，默认 False 不影响其他插件）。
- **plugin_common.js 复核修复（6.2）**：`PluginCommon.request()` 曾与全局 XHR 拦截**双重注入 X-CSRF-Token**（同名头被浏览器逗号拼接为 `token, token`），鉴权模式下写请求后端 CSRF 双提交校验失败返回 403。已移除 `request()` 内手动注入（依赖全局拦截单次注入），浏览器端到端复核确认。
- **AirDrop 插件落地（`plugins/airdrop`）**：局域网文件共享插件（上传/下载/删除/批量删除/批量下载 zip/过期清理/局域网地址/服务端打开上传文件夹），**可配置双模式鉴权**（`configs/airdrop.json` 的 `auth_required`：false 全 public 免登录、true 按权限矩阵），数据目录经配置指向原 AirDrop `uploads`，零迁移。
- 注：以上为 AirDrop 插件化改造期间的文档补充（2026-08-26）。

### 版本说明（v4.2.2 变更，文件传输强化）
- **框架版本升级至 v4.2.2**（`global_var.FRAMEWORK_VERSION`）：统一文件上传与下载能力。
- **全局上传上限兜底（5.6.x / 6.5）**：`app.config['MAX_CONTENT_LENGTH'] = global_var.MAX_UPLOAD_SIZE`（默认 **100MB**，经 config CLI 的 `MAX_UPLOAD_SIZE_MB` 调整）；超限统一返回 413（API 场景 JSON、页面场景模板 `413.html`）。
- **插件级上传限制统一（5.6.x）**：`BasePlugin.max_upload_size` 单位统一为 **MB**（None 回退全局默认）；`save_uploaded_file`/`check_upload_limit` 保存前基于流 seek/tell 预检（不落盘）；**route 级 `max_upload`（MB）覆盖**——权限包装器注入 g 并同步提升本请求 `request.max_content_length`，可突破全局默认（如 AirDrop 的 GB 级大文件路由）。
- **下载能力统一（5.6.x）**：`send_file_response` 增强——中文文件名自动按 **RFC 5987（filename*）** 编码避免乱码、**下载统计**默认计入插件热度（`call_stats[plugin:endpoint]`）、支持 Range 断点续传（206）、`content_disposition_type`/`count_download`/`stats_endpoint` 参数。
- **依赖检查时机（生命周期）**：`on_load` 阶段跨插件依赖检查默认降级为 **warning**（不阻断）；新增 **`on_ready` 就绪钩子**——所有插件加载完成后统一调用（此时 `global_var.plugins` 完整，依赖判断准确）；启用严格模式（`PLUGIN_STRICT_MODE=True`）时依赖确认延后到 `on_ready` 执行。
- **存量迁移**：airdrop `max_gb`（GB）映射为插件级 `max_upload_size`（MB）+ upload 路由声明 route 级 `max_upload`；async_file_demo 声明 `max_upload_size=20`（MB）；下载改走 `send_file_response`（中文名/统计）。
- **回归测试扩充至 18 脚本 331 项**：新增 `test_file_transfer.py`（12 项：全局 413 / 插件级与 route 级上限 / 中文名下载 / 下载统计 / Range / on_ready 顺序），已纳入 CI。

### 版本说明（v4.2.1 变更，框架小修复累计更新）
- **框架版本升级至 v4.2.1**（`global_var.FRAMEWORK_VERSION`）：AirDrop 插件化改造期间的框架小修复正式合入主项目；官方示例 `require_framework_version` 不变（4.2.0 < 4.2.1 仍满足）。
- **插件公开页面豁免正式纳入回归**（`tests/test_framework_fixes.py`）：`public_page=True` 插件页面免登录 200 / 普通插件页面仍守卫 302（auth 已装场景），防 interceptor 豁免逻辑回归。
- **plugin_common.js 双重 CSRF 注入修复固化**：源码静态断言 X-CSRF-Token 注入全文件恰 1 处（全局 XHR send 拦截单次注入），request() 不再手动注入（防同名头逗号拼接 403）。
- **回归测试套件扩充至 17 脚本 319 项**：新增 `test_framework_fixes.py`（public_page 豁免 + CSRF 单值注入 9 项），已纳入 CI。

### 版本说明（v4.2 变更）
- **插件包卸载升级为 installed_files 清单机制**（5.6.6）：安装时把插件引入文件的相对路径清单写入 `plugins/<name>.json`，卸载按清单逐个删除（支持多 `.py` 插件包彻底卸载，无残留），无清单回退旧逻辑（兼容存量插件）。
- **前端工具访问控制**（4.6 / 6.5）：`/frontend/<name>` 页面与 `/frontend-static/` 静态资源按工具的 `permission` 字段做三层校验（`public`/`user`/`admin`，`auth` 未安装时全员放行）；上传/更新缺省 `permission=public`；新增改权限接口 `POST /api/admin/frontend/<name>/permission`；管理后台插件页提供前端工具权限下拉。
- **回归测试套件扩充至 16 脚本 310 项**（12 章）：新增 `test_plugin_cleanup.py`（卸载 installed_files 清单 + clean_old + 越界防御 23 项）、`test_frontend_permission.py`（前端工具三层权限 + 改权限 API + update 保留 permission 25 项）、`test_tools_ops.py`（backup/reset/config 运维工具 19 项）、`test_page_router.py`（大插件多模板页面路由 + 纯 API 无 name 插件调试页回归 21 项），均隔离目录模式、已纳入 CI。
- **公共页面体验升级（8.1）**：首页新增搜索与排序（默认/热度/字母，热度取 API 调用与访问统计）；登录页支持记住用户名、显示/隐藏密码；首页/登录/登出/裸插件调试四页面样式统一为 `static/css/main.css` 设计体系，脚本抽离至 `static/js/`。
- **裸插件调试页增强（8.1）**：支持**路径参数**输入与替换（`<name>`/`<int:name>`，如 async_file_demo 的 `/status/<task_id>`）；**非安全方法自动携带 X-CSRF-Token**（修复带鉴权接口无法调试的 CSRF 403）；PUT/DELETE 改发 JSON body；展示 HTTP 状态/耗时/业务 code/实际 URL；结果一键复制与折叠、会话内请求历史。
- **框架版本升级至 v4.2.0**（`global_var.FRAMEWORK_VERSION`）：页面路由 page=True / 模板命名空间 / render·render_index 助手（见 5.5.1）等大插件多模板能力随 v4.2 对齐；官方示例 `require_framework_version` 同步为 4.2.0。

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
│   ├── plugin_scanner.py      #   插件静态扫描器（AST 后端扫描 + 前端 HTML 扫描，10.6）
│   ├── capabilities.py        #   插件能力声明模型（解析/匹配/交叉校验/运行时授权，10.7）
│   ├── audit_hook.py           #   运行时审计钩子（sys.addaudithook，10.8）
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
├── examples/                  # 官方示例插件/工具包（7 个）+ install_all.py 一键安装
├── tools/                     # 开发运维命令行工具（python tools/xxx.py）
│   ├── config.py              #   配置管理 CLI（show/set/unset/reset/check/env/profile 预设）
│   ├── scan.py                #   插件静态扫描 CLI（.py / .zip / 目录，--json）
│   ├── package.py             #   插件包打包/签名/校验 CLI（genkey/pack/verify/show）
│   ├── backup.py              #   手动备份/恢复工具（Factory Reset 前备份关键数据）
│   ├── gen_cert.py             #   HTTPS 自签名证书生成工具（v4.5.0，openssl）
│   └── reset.py               #   深度重置工具（服务停止时使用，绕过运行时文件锁定）
├── tests/                     # 回归测试套件（22 脚本 482 项 + 端到端链路验证）
├── templates/                 # 页面模板（首页/登录/错误码页 400-500/admin 管理后台/插件页）
│   ├── admin/                 #   管理后台（dashboard / plugins / logs / stats / system）
│   ├── frontend_tools/        #   前端工具模板
│   └── plugins/               #   插件页面模板
├── static/                    # 静态资源（css/main.css 统一设计体系 + error.css 错误页；js/plugin_common.js 统一鉴权前端 + main.js 公共脚本 + index/login/plugin_default/logout 页面脚本）
├── .github/workflows/ci.yml   # GitHub Actions CI 工作流
├── data/                      # 运行时数据（统计/审计/用户配置，已 gitignore）
├── logs/                      # 运行日志（已 gitignore）
├── documents/                 # 开发规范 / Roadmap / CI 上手指南 / 版本收尾 checklist
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
| `capabilities` | 否 | 能力白名单声明（v4.3.2，字符串列表）；未声明的检出行为在 enforce 模式下拒绝安装，见 10.7 |

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
- **声明了**：上传/更新时与 `global_var.FRAMEWORK_VERSION`（当前 `4.2.0`）做点分版本比较（`compare_versions`，修复了前端工具原先字符串比较的缺陷）；插件要求高于框架版本 → 拒绝安装并报告。
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
| 登录 | `/login` | 记住用户名（localStorage）、显示/隐藏密码、回车提交、防重复提交、登录成功页 + redirect 安全回跳（拒绝站外与 `/login` 自身）；**429 登录锁定冷却（v4.3.0）**：展示后端通用信息并禁用登录按钮 30s（前端固定冷却，不泄露后端实际锁定剩余时间） |
| 登出 | `/logout` | 调用登出接口清理 Cookie + 成功页（自动/手动跳转登录） |
| 裸插件调试 | `/plugin/<name>`（无自定义模板时） | 列出插件全部 API 与参数（string/boolean/file/array/object **+ 路径参数 `<name>`/`<int:name>` 输入框**），可视化调用并展示 JSON 结果（**HTTP 状态码/耗时/业务 code/实际请求 URL**）；**非安全方法自动携带 CSRF**；**PUT/DELETE 与 POST 一致发 JSON body**；一键复制/折叠结果、请求历史；属插件测试工具，功能改动需谨慎 |

> **/plugin/ 页面登录守卫**：auth 插件已安装时，`/plugin/` 下所有页面默认需登录（全局 `before_request` 守卫，未登录跳转登录页携带 redirect）。插件声明 `public_page=True` 可豁免（见 4.5.1）；`/static/` 静态资源始终公开。

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

### 10.2 系统安全配置（v4.3.0）

框架提供系统级安全开关（`global_var` 配置项，经 `tools/config.py` 调整，见 8.1）：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `SECURITY_HEADERS` | `True` | 统一注入安全响应头（X-Content-Type-Options / X-Frame-Options / CSP / Referrer-Policy / Permissions-Policy）并移除 Server / X-Powered-By 指纹头 |
| `SESSION_COOKIE_SECURE` | `False` | 会话 Cookie 加 Secure 属性（仅 HTTPS 生效；HTTP 局域网部署保持 False，否则浏览器丢弃 Cookie） |
| `LOGIN_MAX_ATTEMPTS` | `5` | 登录连续失败锁定阈值（次） |
| `LOGIN_LOCK_SECONDS` | `900` | 登录失败锁定时长（秒，默认 15 分钟） |
| `LOGIN_LOCK_MODE` | `ip_username` | 登录锁定维度：`username`=仅用户名 / `ip_username`=IP+用户名（默认，防分布式爆破）/ `off`=禁用锁定（不安全，仅信任局域网时使用） |
| `SESSION_IDLE_TIMEOUT` | `1800` | 会话空闲超时（秒，默认 30 分钟；超过未活动即失效） |
| `PLUGIN_SCAN_MODE` | `report` | 插件安装校验门禁（v4.3.1 静态扫描 + v4.3.2 capabilities 交叉校验）：`off` 跳过 / `report` 放行附摘要（默认） / `enforce` 高风险或未声明行为拒绝安装，详见 10.6 / 10.7 |
| `AUDIT_HOOK_MODE` | `observe` | 运行时审计钩子（v4.4.0）：`off` 不安装 / `observe` 记录不阻断（默认） / `enforce` 未授权行为阻断（网络白名单即防火墙），详见 10.8 |
| `SSL_CERT_FILE` | `` | HTTPS 证书 PEM 文件路径（v4.5.0，`kind=path`）；与 `SSL_KEY_FILE` 均配置且存在时启用 HTTPS，默认空=HTTP，生成自签名证书见 `tools/gen_cert.py`（10.9） |
| `SSL_KEY_FILE` | `` | HTTPS 私钥 PEM 文件路径；与 `SSL_CERT_FILE` 配对，仅配一项时回退 HTTP 并告警 |

**登录失败锁定行为**：锁定期间登录接口统一返回 HTTP 429 与通用错误信息（不泄露锁定剩余时间等细节）；登录成功后自动清除对应维度的失败计数；锁定计数仅存内存（重启即清零）。

**手动解封（v4.5.1）**：管理员可在 user_manage 用户管理页查看各用户锁定状态（列表 `locked` 字段）并**一键解封**（`POST /api/user_manage/unlock`，admin 权限）——清除该用户名全部维度（username / ip_username）锁定记录，无需等待锁定期满即可立即登录；解封不存在用户返回 404，解封未锁定用户幂等返回提示。

### 10.3 上传大小限制

- 管理后台上传的**后端插件包**与**前端工具包**统一受 `global_var.PACKAGE_MAX_UPLOAD_SIZE`（默认 10MB）限制，超限返回 `413 Payload Too Large`。
- 插件自身提供的「数据上传」接口大小由插件通过 `BasePlugin.max_upload_size` 自行约束（默认 10MB）。

### 10.4 Factory Reset（恢复出厂设置）

- 设计意图：将部分/全部框架数据还原至安装初始状态，**不提供自动备份**（数据丢失由用户自行承担）。
- **此操作不可逆**：执行前请务必手动备份关键数据（`plugins/configs/`、`data/`、`frontend_tools.json` 等）。
- 管理后台重置弹窗已内置「不可撤销、请先备份」的风险提示，确认后才会执行。
- 内置插件（`auth`、`user_manage`）在重置中受保护不被删除；`all` 范围会重置其配置（auth 恢复默认 `admin/admin123`）。

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

| 模式 | 行为 |
|------|------|
| `off` | 跳过扫描 |
| `report`（默认） | 放行安装，响应附 `scan` 摘要与 `scan_scope` 范围，审计日志记录 |
| `enforce` | 检出高风险（high > 0）即拒绝安装，返回 400 附完整 `scan_report`，审计日志记录 blocked |

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

| 预设 | 定位 | 关键差异 |
|------|------|---------|
| `daily` | 日常使用（默认基线） | 扫描 report、完整性 warn、锁定 ip_username 5 次/15 分钟、Cookie Secure 关 |
| `strict` | 运维加固（需 HTTPS） | 扫描 enforce、完整性 strict、依赖严格、锁定 3 次/30 分钟、空闲 15 分钟、Cookie Secure 开 |
| `lan-open` | 可信局域网开放 | 扫描 off、登录锁定 off（仅在内网用户与插件来源完全可信时使用） |

```bash
python tools/config.py profile daily    # 套用预设（返回变更清单）
python tools/config.py set PLUGIN_SCAN_MODE enforce   # 单项覆盖
```

---

### 10.7 插件能力声明（capabilities，v4.3.2，P1 阶段二）

插件在 plugin.json 中以可选字段 `capabilities` 声明**白名单授权**（扁平字符串列表，语法 `域:子域:参数`），安装时与静态扫描的行为范围（10.6）交叉校验。核心哲学：**Deny by Default，声明即授权**——扫描器输出的是"事实"，capabilities 是"授权"，两者比对产生 mismatch 清单。

**能力目录（8 大域，开放集合）**：

| 域 | 能力项 | 语法 | 授权语义 |
|----|--------|------|---------|
| filesystem | 读 / 写 | `filesystem:read:<path>` / `filesystem:write:<path>` | 路径前缀授权（目录级含子内容；`data`、`data/`、`data/*` 三写法等价；支持绝对路径与 UNC） |
| network | HTTP 出站 | `network:http:<scheme://host[:port][/path*]>` | host 精确或 `*.dom` 子域通配（**禁裸 `*`**）；声明带端口须精确，不带=任意；path 前缀 |
| | TCP/UDP | `network:tcp:<host[:port]>` / `network:udp:...` | host 精确；无端口=任意端口 |
| | 监听服务 | `network:server:<host:port>` | 插件 bind/listen 监听端口 |
| webhook | 群机器人 | `webhook:<platform>:<url-pattern>` | 平台枚举 wecom/dingtalk/feishu；URL 语义同 network:http（兼作 HTTP 出站授权） |
| process | 子进程 | `process:exec` / `process:exec:<bin>` | 无参=任意子进程（高危）；带 bin=仅该可执行名（运行时比对） |
| scheduler | 定时任务 | `scheduler` | 允许注册 APScheduler 任务 |
| database | 数据库 | `database:sqlite:<path>` / `database:mysql:<host:port/db>` / `database:postgres:...` | 连接目标 |
| device | 串口/打印 | `device:serial:<port>` / `device:print` | 串口枚举（如 COM3） |
| env | 环境变量 | `env:read:<pattern>` | 变量名前缀或 `*` 通配 |

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

| 路径 | 说明 |
|------|------|
| `plugins/configs/<name>.json` | 基类 `load_config()` / `save_config()` |
| `plugins/data/<name>/**` | 插件专属数据目录（`self.data_dir` / `self.get_data_path()`） |
| `plugins/temp/<name>/**` | 插件专属临时目录 |

跨插件目录（如插件 A 写 `plugins/data/B/`）与 `data/`（框架自身数据）**不在豁免范围**，仍须显式声明。基类 `get_data_path()` 拼接写法扫描器提取不到路径字面量，该盲区由运行时审计钩子（4.4.0）以 `check_filesystem()` 兜底。

**交叉校验与门禁**（并入 `PLUGIN_SCAN_MODE`，与静态扫描共用三档）：

| 模式 | 行为 |
|------|------|
| `off` | 跳过扫描与能力校验 |
| `report`（默认） | 放行，响应附 `capabilities`（`declared` 已声明 / `missing` 未声明 / `suggested` 建议声明） |
| `enforce` | 高风险（high > 0）**或** `missing` 非空 → 400 拒绝，附完整缺失清单与建议声明 |

**建议声明自动生成**：`suggested` 字段按检出行为归一化生成（文件路径→父目录、URL→主机根、端口/子进程→对应能力项），可整段复制回 plugin.json，降低声明编写门槛；声明了但未检出使用的能力仅 `unused` 提示（info 级，不阻断），鼓励最小授权。

**运行时授权基准**：插件加载时 loader 从描述文件读取 capabilities 注册进 `core/capabilities.py` 内存注册表；`check_filesystem(plugin, path, mode)` / `check_network(plugin, endpoint)` / `check_process(plugin, bin)` 为 4.4.0 运行时审计钩子的授权判定契约——`check_network` 的 host 匹配即网络白名单"防火墙"规则。未注册/未声明一律拒绝（fail-closed）。

**向后兼容**：旧插件无 `capabilities` 字段——report 模式放行附告警；enforce 模式下若有未声明检出行为则拒绝（良性插件扫描范围通常为空，不受影响）。plugin.json 在 manifest.json 完整性清单内，装后私改 capabilities 会被完整性校验拦截。

> **官方示例维护约定**：`examples/` 下的示例插件须与最新开发规范保持同步——`require_framework_version` 需高于所用框架 API 的引入版本（如使用 `get_data_path` 的示例要求 ≥ 4.3.2）；示例内容变更时同步升级 `version`（plugin.json 与插件类属性两处一致，见 5.6.3），保证 `update` 可重复安装。综合示例 `corp_tools`（企业内网工具箱）演示 capabilities 网络白名单与权限过滤导航，设计见 `documents/插件设计-corp_tools.md`。

---

### 10.8 运行时审计钩子（v4.4.0，P1 阶段三）

基于 CPython 原生 `sys.addaudithook` 的运行时防线（`core/audit_hook.py`）：插件**执行期间**的敏感操作被实时拦截并判定，与安装期两条防线（10.6 静态扫描、10.7 能力声明）构成纵深防御第三层。

**监听事件与能力映射**（Windows/CPython 实测验证）：

| 事件 | 能力映射 |
|------|---------|
| `open` / `io.open`（读模式） | `filesystem:read` |
| `open`（写模式） / `os.remove` / `os.unlink` / `os.rmdir` / `shutil.rmtree` / `os.mkdir` / `os.makedirs` | `filesystem:write` |
| `os.system` / `subprocess.Popen` / `os.exec*` / `os.spawn*` | `process:exec` |
| `socket.connect` | `network`（http 声明隐含允许 TCP 连接该 host；否则按 `tcp://host:port` 比对） |
| `socket.bind` | `network:server` |
| `sqlite3.connect` | `database:sqlite` |

**归属判定**：审计事件触发时遍历调用栈，定位 `plugins/<name>.py` 帧（去 `.py` 后缀）；`base_plugin` 等框架内置帧不计为插件来源；解释器内部路径（stdlib/site-packages/`__pycache__`）读取直接跳过（非插件业务）。栈中无插件帧 → 视为框架自身行为放行。

**授权判定**：复用 4.3.2 注册的能力集与 `check_filesystem`（含自属路径隐式豁免）/`check_network`/`check_process`/`check_database`，未注册/未声明一律拒绝（fail-closed）。

**模式 `AUDIT_HOOK_MODE`**：

| 模式 | 行为 |
|------|------|
| `off` | 不安装钩子（零开销） |
| `observe`（默认） | 未授权行为聚合计数 + 后台线程写审计 JSONL，不阻断 |
| `enforce` | 未授权行为抛 `RuntimeError`（消息含插件名与建议声明）阻断，插件可捕获 |

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
| `test_page_router.py` | 大插件多模板（页面路由 page=True：主入口自动检测、dict/Response 分发、路径参数注入、正斜杠模板名、旧式 page() 兼容）+ 纯 API 无 name 插件调试页回归 | 21 项 |
| `test_framework_fixes.py` | 框架小修复（v4.2.1）：public_page 豁免（公开页面免登录 200 / 普通插件页面守卫 302）+ plugin_common.js CSRF 单值注入静态断言 | 9 项 |
| `test_file_transfer.py` | 文件传输强化（v4.2.2）：全局 413 / 插件级 max_upload_size 预检 / route 级 max_upload 覆盖 / 中文名下载 / 下载统计 / Range / on_ready 顺序 | 12 项 |
| `test_security.py` | 系统安全回归（v4.3.0）：安全响应头注入与开关 / 指纹头移除 / Cookie HttpOnly+SameSite+Secure 联动 / 会话空闲超时 / 登录失败锁定三档（ip_username/username/off）+ 通用 429 + 成功重置 | 30 项 |
| `test_plugin_scan.py` | 插件静态扫描回归（v4.3.1）：扫描器单元（危险导入/调用/混淆/范围提取/别名归因）/ 插件包扫描 / 前端 HTML 扫描 / enforce 门禁集成（拒绝 400 + 附报告 + 未落盘 + 真实项目未污染）/ 配置预设三套 | 35 项 |
| `test_capabilities.py` | 插件能力声明回归（v4.3.2）：解析器（合法/非法/未知域/裸 * 拒绝）/ 匹配语义（路径前缀递归/URL host·path·端口/子域通配/tcp/env）/ 交叉校验（隐式豁免/跨插件越界/建议声明/unused）/ 运行时授权 API（fail-closed/process 细粒度）/ 安装链路集成（enforce 拒绝与放行/响应附摘要/loader 注册）/ base_plugin data API + hello_plugin 示例端到端 | 51 项 |
| `test_audit_hook.py` | 运行时审计钩子回归（v4.4.0）：事件映射（open 读写/删除族/sqlite/socket）/ 栈定位（plugins 帧/框架放行/嵌套归因）/ observe 聚合（按插件/建议声明/事件样本）/ enforce 阻断（异常传播/授权放行/自属豁免/fail-closed）/ 隔离集成（真实钩子+栈归因端到端/stats 按插件分组/重载清零/审计落盘/未污染） | 36 项 |

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
python tests/test_page_router.py       # 21 项（大插件多模板页面路由 + 纯 API 无 name 插件调试页回归，隔离目录）
python tests/test_framework_fixes.py    # 9 项（public_page 豁免 + CSRF 单值注入，隔离目录）
python tests/test_file_transfer.py       # 12 项（文件传输强化，隔离目录）
python tests/test_security.py            # 30 项（系统安全回归 v4.3.0，隔离目录）
python tests/test_plugin_scan.py           # 35 项（插件静态扫描回归 v4.3.1，隔离目录）
python tests/test_capabilities.py          # 51 项（插件能力声明回归 v4.3.2，隔离目录）
python tests/test_audit_hook.py            # 36 项（运行时审计钩子回归 v4.4.0，隔离目录）
# 合计 22 个脚本 482 项
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
| `PLUGIN_SCAN_MODE` | report | 插件安装静态扫描门禁（off/report/enforce，见 10.6，v4.3.1） |
| `PLUGIN_PUBLIC_KEY_PEM` | （空） | 插件签名公钥路径 |

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
