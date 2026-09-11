# FlaskToolkit 自签名 HTTPS 与反向代理稳定性评估报告

- 评估日期：2026-09-06
- 评估版本：v4.11.0（含 v4.12 反代支持增量）
- 评估环境：Windows 11（Git Bash）、Python 3.12、Chrome（cdp-use）、OpenSSL（Git for Windows 自带）、Nginx 1.30.4（Windows 官方包）

## 一、评估范围

| 场景 | 说明 |
|------|------|
| 直连自签名 HTTPS | `tools/gen_cert.py` 生成证书 → `SSL_CERT_FILE`/`SSL_KEY_FILE` 启用，浏览器直接访问 |
| 反向代理（Nginx TLS 终止） | Nginx 443/8443 终止 TLS → `proxy_pass` 框架内部 HTTP 5010 → 框架开启 `TRUST_PROXY_HEADERS` + `EXTERNAL_SCHEME`/`EXTERNAL_PORT` |

## 二、直连 HTTPS 验证结果（全部通过）

| 检查项 | 结果 |
|--------|------|
| TLS 握手 | ✅ TLSv1.3 / TLS_AES_256_GCM_SHA384（Werkzeug dev server 标准行为） |
| 证书内容 | ✅ CN=localhost，SAN: `DNS:localhost, IP:127.0.0.1`，1 年期（gen_cert 默认 --days 3650，本次 365） |
| curl 校验行为 | ✅ 不带 `-k` → exit 60（自签名不受信任，预期）；`-k` → 200 |
| 浏览器首次访问 | ✅ 证书警告页（NET::ERR_CERT_AUTHORITY_INVALID）→ Advanced → 继续前往 → 正常进入 |
| 登录/后台 | ✅ 登录成功 → dashboard / system / network 页完整渲染 |
| scheme 联动 | ✅ 启动横幅 `https://127.0.0.1:5010`；网络页「协议 HTTPS」；二维码内容 `https://127.0.0.1:5010`；mDNS 提示 `https://<主机名>.local:端口` |
| 混合内容 | ✅ 0 个 http:// 资源（全部相对路径 + https 外部链接） |
| HTTP 直连 | ✅ 连接失败（仅 https 端口监听，无自动 http→https 跳转——记录项 R1） |

## 三、反向代理（Nginx TLS 终止）验证结果（全部通过）

| 检查项 | 结果 |
|--------|------|
| 链路 | ✅ Nginx 8443（TLS）→ 框架 5010（内部 HTTP），双层均 200 |
| 反代头信任 | ✅ 启动日志「已启用反向代理头信任（TRUST_PROXY_HEADERS=true）」；ProxyFix 单测通过 |
| 外部协议 | ✅ 网络页「协议 HTTPS」（EXTERNAL_SCHEME=https 生效，无请求上下文也正确） |
| 外部端口 | ✅ 分享入口 `https://127.0.0.1:8443`（EXTERNAL_PORT=8443，二维码/复制链接同步） |
| 登录流程 | ✅ 经 Nginx 登录/后台/网络页完整可用 |
| 上传大小 | ✅ 5MB POST 经 Nginx 放行至框架（`client_max_body_size 100m` 生效；默认 1MB 会挡 100MB 上传） |

## 四、发现的问题与处置

### 已修复（本评估落地）

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| F1 | P1 | 反向代理 TLS 终止时框架内部 HTTP，`get_scheme()` 只看 SSL_CERT_FILE → 横幅/分享链接/二维码全变 `http://`，分享出去的链接不可达 | 新增 `EXTERNAL_SCHEME` 配置（https/http/空），`get_scheme()` 优先读取；加载 user_config 后生效 |
| F2 | P1 | 代理后 `request.remote_addr` 全为 127.0.0.1 → 审计日志失去来源 IP、登录锁定 `ip_username` 维度退化 | 新增 `TRUST_PROXY_HEADERS` 配置，开启时注册 Werkzeug ProxyFix（x_for/x_proto/x_host=1），审计/public/auth 全部自动受益 |
| F3 | P2 | 反代场景分享地址 host:port 为内部值（如 `https://127.0.0.1:5010`），外部 8443 不可达 | 新增 `EXTERNAL_PORT`（外部端口）与 `EXTERNAL_HOST`（外部域名，可选）；`get_access_urls`/`get_mdns_url` 输出外部入口（kind=external 置顶） |
| F4 | P2 | 证书/私钥无效或不匹配时 `app.run` 内部 ssl.SSLError 裸崩溃无提示 | 新增 `validate_ssl_cert()` 起服前预校验（PEM 可读 + key/cert 配对），失败友好报错退出；证书过期仅 warning 不阻断（浏览器会提示） |
| F5 | P2 | 网络页 mDNS 提示硬编码 `http://`（HTTPS 下误导）；该词条缺 en 翻译 | 词条改 `{scheme}` 插值（页面路由传 scheme），en.json 补翻译（114 词条） |

### 已记录（本期不修，见风险清单）

| # | 级别 | 问题 |
|---|------|------|
| R1 | P3 | 无 http→https 自动跳转；http:// 直连直接失败（可用 Nginx `return 301 https://$host$request_uri` 兜底，已写入 3.4 示例的部署说明） |
| R2 | P3 | 会话/CSRF Cookie 默认无 Secure 属性（SESSION_COOKIE_SECURE 默认 False，兼容纯 HTTP 局域网）；HTTPS/反代部署需手动 `config set SESSION_COOKIE_SECURE true`（3.4 已引导） |
| R3 | P3 | 自签名证书不被系统信任，每次设备首次访问需手动接受；局域网多设备建议导入 CA 或接受提示（iOS/Android 对自签名限制不同，二维码扫码分享场景需提示） |
| R4 | P3 | 私钥明文（gen_cert `-nodes`），文件权限需自行保护（.gitignore 已排除 data/certs/ 与 reverse_proxy_test/） |
| R5 | P3 | 子路径挂载（`location /ft/`）不支持，须根路径反代（3.4 注明） |
| R6 | P3 | 客户端 IP 归因端到端验证受本机单点限制（无法制造外部 IP），以 ProxyFix 单测 + 启动确认替代；多机环境建议复测 |

## 五、测试与回归

- `tests/test_network.py`：24 → **34 项**（+H 组 EXTERNAL_SCHEME 5 项 + I 组 EXTERNAL_HOST/PORT 5 项）
- `tests/test_admin_api.py`：60 → **62 项**（+ProxyFix 注册/关闭 2 项；补 AUDIT_LOG_FILE 隔离防写真实 audit.log）
- 全量回归：**32 脚本 791 项 0 失败**
- 回归数字口径：779 → 791（+12）

## 六、结论

框架在**自签名 HTTPS 直连**与 **Nginx 反向代理（TLS 终止）** 两种部署下运行稳定：scheme 推导、分享链接/二维码、登录鉴权、审计 IP 归因、上传链路均正确。本评估落地了 5 项修复（2 项 P1 反代核心 + 3 项 P2 完善），剩余风险均为 P3 部署提示级，不构成阻断。Werkzeug dev server 为开发服务器，生产高并发场景建议经 Nginx 反代（本评估验证路径）或切换生产 WSGI（gunicorn/waitress + TLS），属部署建议非框架缺陷。
