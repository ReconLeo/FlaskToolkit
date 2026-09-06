# test_server/ — FlaskToolkit 压力与多机归因测试工具

承接 `documents/HTTPS与反向代理稳定性评估-2026-09-06.md` 的 **阶段 3（并发/大文件/长稳压力）** 与 **阶段 4（多机 IP 归因复测）**。本目录为测试脚手架，与框架运行时隔离，不进入框架 core/plugins 目录。

## 目录结构

```
test_server/
├── README.md              # 本文件
├── android_client.py      # Android（Pydroid）端测试客户端：probe / stress / upload 三模式
├── android_server.py      # （可选）Android 端 Flask 微型服务器，反向链路诊断
├── pc_stress.py           # PC 端并发/大文件压测（标准库 urllib + threading）
├── pc_collect.py          # PC 端长稳采集（psutil；每 60s 记录进程指标，10min 心跳）
├── fixtures/
│   ├── echo_upload/       # 回显上传测试插件源码（plugin.json + echo_upload.py）
│   └── build_echo_plugin.py  # 构建 echo_upload.zip 的脚本
└── diagnostics/           # 诊断输出/回传目录（已 gitignore，不入库）
```

## 前提

- PC 与 Android **同一局域网/WiFi**（Android 直连 PC 局域网 IP；跨网段将无法测试）
- PC 端框架以 **直连 HTTPS**（SSL_CERT_FILE/SSL_KEY_FILE）或 **Nginx 反代**（8443）方式运行
- Android 端 Pydroid：Python 3.13.2 + requests（本机已装 2.34.2）；如缺失执行 `pip install requests`
- PC IP 获取：框架启动横幅/后台「网络与访问」页，或 `ipconfig` 找 IPv4 地址

## Android 端用法（Pydroid 内运行）

```bash
# 1) 归因探测（默认）：登录 + 访问各端点，输出诊断 JSON 到 diagnostics/
python android_client.py --base https://192.168.1.100:5010 --user admin --password admin123

# 2) 并发压测：登录态 50 并发 × 3 轮打混合 API
python android_client.py --mode stress --base https://192.168.1.100:5010 --concurrency 50 --rounds 3

# 3) 大文件上传：上传 100MB 到 echo-upload 插件（需先安装 fixtures/echo_upload.zip）
python android_client.py --mode upload --base https://192.168.1.100:5010 --size-mb 100

# 反代链路：--base 换为 https://192.168.1.100:8443（PC 上 Nginx 反代端口）
```

输出：终端摘要 + `diagnostics/android_<mode>_<时间戳>.json`。**把该 JSON 文件回传到 PC 的 `test_server/diagnostics/` 目录**，框架侧比对审计日志 remote_addr 是否等于 Android 的局域网 IP（多机 IP 归因验证）。

## PC 端用法（Git Bash）

```bash
# 3A 并发压测（直连 HTTPS）
python test_server/pc_stress.py --base https://127.0.0.1:5010 --scenario mixed --concurrency 100 --rounds 3
python test_server/pc_stress.py --base https://127.0.0.1:5010 --scenario login --concurrency 50
python test_server/pc_stress.py --base https://127.0.0.1:5010 --scenario upload --concurrency 10

# 3C 长稳采集（后台运行，--hours 12）
python test_server/pc_collect.py --base https://127.0.0.1:5010 --hours 12 &
```

## 回显上传测试插件（阶段 3B 大文件载体）

框架无内置大文件接收端点（插件包上限 10MB、全局 MAX_CONTENT_LENGTH 100MB），故提供隔离测试插件：

```bash
python test_server/fixtures/build_echo_plugin.py          # 生成 echo_upload.zip
# 在框架后台「插件管理」上传安装（或 API /api/admin/plugins/upload，preview=1 能力确认后 confirm=1）
# 测完卸载：后台卸载 + 清理（purge-data），源码与 zip 均在 test_server/fixtures/ 不入库
```

插件路由：`POST /api/echo-upload`（multipart 单 file 字段）→ 落盘到 `plugins/data/echo_upload/` 并返回 `{size, sha256, saved}`；`GET /api/echo-upload/<name>` 回传文件供下载校验哈希一致性。

## 诊断回传约定

- Android 端产物：`test_server/diagnostics/android_*.json`
- PC 端产物：`test_server/diagnostics/longrun_*.jsonl`、`stress_*.json`
- 框架侧配合材料：`data/audit.log` 相关片段（多机归因比对用）
- 评估报告由 PC 端汇总落盘 `documents/`

## 安全注意

- 所有请求 `verify=False`（自签名证书仅限测试），**勿用于生产**；诊断 JSON 含响应头，不落凭据明文
- echo_upload 插件仅测试用，用完卸载并 purge-data；上传文件存于 `plugins/data/echo_upload/`，卸载清理
- Android 浏览器访问自签名 HTTPS 时需手动接受证书（R3），与桌面浏览器流程不同，属已知事项
