# FlaskToolkit v4.23.4

自签名证书生成的环境兼容修复：修掉"某些发行版的 openssl 缺默认 `openssl.cnf` 导致 `tools/gen_cert.py` 必然失败"的问题。全量回归 49 脚本 0 失败。

## 问题

部分发行版把 openssl 的 `OPENSSLDIR` 写死成**构建机路径**（典型：conda 打包的 OpenSSL，`openssl version -a` 显示 `OPENSSLDIR: "D:\bld\openssl_split_*\...\Library"`）。默认配置 `<OPENSSLDIR>/openssl.cnf` 在本机并不存在，于是 `openssl req` 在**库初始化阶段**（早于命令行解析）就报错退出：

```
Can't open "D:\bld\openssl_split_1683022585232\_h_env\Library/openssl.cnf" for reading, No such file or directory
```

实测结论（v4.23.4 修复前）：

- 传 `-config <file>` **救不回来**——命令行参数晚于库初始化读配置；
- 只有环境变量 **`OPENSSL_CONF`** 生效；
- **影响面仅限"生成自签名证书"**：HTTP 是默认且不需要证书；HTTPS 运行时走 Python `ssl`（libssl 不读 openssl.cnf，本地 TLS 握手实测正常）；`SSL_CERT_FILE/SSL_KEY_FILE` 指向坏文件时 `app.py` 本就会告警并回退 HTTP。受损的是"一键启用 HTTPS"——CLI 吐 openssl 原始 stderr，桌面启动器 HTTPS 复选框在 Tk 回调里裸抛 `RuntimeError`（GUI 看起来毫无反应）。

## 修复

**`tools/gen_cert.py` 新增 `_run_openssl()`**：首次按系统默认配置执行；**仅当**失败特征命中「`Can't open` + `openssl.cnf`」时，写一份**临时空配置**并注入 `OPENSSL_CONF` 重试一次（CN/SAN/days 全部由命令行显式传入，空配置足够），成功后 stderr 打一行提示。

设计取舍：

- **不做无条件注入**：健康机器首次即成功、行为与原先完全一致；也避免覆盖用户/企业的 `OPENSSL_CONF`（FIPS 等依赖配置的场景）；
- **不做无脑重试**：非「配置缺失」类失败（如密钥不可写）不重试，不掩盖真实错误（有专项断言）；
- **不引入 `cryptography` 兜底**：与"仅用 stdlib + 系统 openssl"的既有取向一致，新增依赖的包体与供应链成本不划算；
- 失败报错改为带 openssl 路径 + 三条排查路径（设 `OPENSSL_CONF` / 换 Git for Windows 或 OpenSSL-Win64 的 `openssl.exe` / 用其他工具签发后配 `SSL_CERT_FILE`）。

**`tools/desktop_launcher.py`**：GUI `on_start` 捕获 `RuntimeError` 并弹窗提示「可取消勾选 HTTPS 后以 HTTP 启动」，不再在 Tk 回调里裸抛异常导致按钮无响应。

## 升级建议

用 `OPENSSL_CONF=<有效路径>` 可消除兜底提示；或把 Git for Windows / OpenSSL-Win64 的 `openssl.exe` 放到 PATH 前面。已生成的证书与既有 HTTPS 配置不受影响，无需迁移。

## 测试与文档

- `test_desktop_launcher.py` 36→40 项（+配置缺失时重试一次 / 重试注入临时 `OPENSSL_CONF` / 兜底成功返回 0 / 非配置类失败不重试）。
- 开发规范 14.4 新增「openssl 默认配置缺失的兜底」小节（含 `-config` 无效的实测结论与影响面说明）；README 双版断言数同步 49 脚本 / 1355 项断言。

**全量回归 49 脚本 0 失败。**

- **Runtime**: `FlaskToolkit-4.23.4-runtime.zip`（精简运行包，116 条目含 manifest.json）
- **sha256**: `56d117c51adeff029bf5e95bf51843278afccd62c02e18d76afc5fc5c564819a`
