# FlaskToolkit

<p align="center">
  <img src="https://github.com/ReconLeo/FlaskToolkit/actions/workflows/ci.yml/badge.svg" alt="CI">
  <img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
  <img src="https://img.shields.io/badge/version-4.5.1-blue" alt="Version">
</p>

> 一个基于 Flask 的插件化**框架**：把散落的 Python 插件与纯前端工具装进统一的运行时，
> 动态安装、热重载、权限可控。自己写的、自己维护的、只跑在本地——不依赖云、不上传数据。
>
> **English**：[English](README.md) · **中文**：本页

## 为什么会有 FlaskToolkit（作者自述）

我写过很多"小玩意儿"：签到脚本、定时任务、文件处理、图表页……大多是 Python 写的，其中不少是 Flask 前后端一体的页面，也有不少是纯前端的 HTML。它们各自都好用，但都散落在各个文件夹里——每次想加个新功能，就得把登录鉴权、上传下载、页面骨架、定时任务这些轮子重新造一遍。

更让我在意的是：越来越多本该轻巧的事情，被搬到了网上——离线就不能用，还悄悄收集我的数据。我不想为了一个内部小工具去注册账号、接受隐私政策。我想要的，是跑在自己电脑上（顶多局域网里几个人能用）的小程序。

于是就有了 FlaskToolkit：一个插件化**框架**——而不是又一个重复造轮子的工具站。它把我这些"自留地"小程序，连同各自的能力，装进一套可复用、可扩展的"地基"里。

它慢慢长成了现在的样子：

- 从单文件插件，长出了**插件包（.zip）**——插件连同自己的模板、静态资源一起分发，安装即用；
- 纯前端的 HTML 小工具，也能作为"一等公民"装进来，和 Python 插件平起平坐；
- 大插件也能拆得清清爽爽——**多模板 + 辅助模块 + 静态资源**，一个插件可以有自己的子页面、工具模块与样式脚本（页面路由 page=True）；
- 有了统一的三层权限、可选鉴权、审计日志、热重载——页面改了保存即生效，不用重启；
- 统一了文件传输能力——**全局上传大小上限（默认 100MB，route 级可覆盖）** + 保存前流式预检、中文文件名下载不乱码（RFC 5987）、下载统计与 Range 断点续传；
- 系统安全强化——**统一安全响应头**（CSP / X-Frame-Options / nosniff / no-referrer，隐藏服务器指纹）、**会话 Cookie 加固**（HttpOnly + SameSite + 可选 Secure）、**登录失败锁定**（IP+用户名维度、锁定期间通用 429、阈值可配置）与会话空闲超时；
- 安装即安检：基于 AST 的**插件静态扫描器**在上传插件包 / 前端工具包时自动审查——危险导入与调用（subprocess、pickle、动态执行）、混淆、网络与文件触点都会被标记，门禁支持 off / report / enforce 三档，另附日常 / 运维加固 / 局域网开放三套一键配置预设；
- 能力声明即授权：插件在 plugin.json 里声明白名单——可读写的路径、可访问的网络端点、子进程、定时任务、数据库、设备、环境变量——安装时与扫描结果交叉校验，enforce 下未声明即拒绝（附自动生成的建议声明），插件自属的配置/数据/临时目录隐式豁免免声明，解析后的授权集成为运行时防线基准；
- 运行时审计防线：基于 sys.addaudithook 的**运行时守卫**拦截插件代码的敏感操作——文件读写删除建目录、子进程、socket 连接/监听、sqlite——经调用栈定位归属插件、按其声明授权判定（网络白名单即"防火墙"）；off / observe / enforce 三档可调，未授权行为按插件聚合展示于管理后台并附可复制的建议声明；
- 可选 HTTPS：配置 `SSL_CERT_FILE` / `SSL_KEY_FILE` 指向证书与私钥（`python tools/gen_cert.py` 一键生成自签名证书）即以 HTTPS 启动服务，默认仍是 HTTP；前端工具注册清单 `frontend_tools.json` 默认路径迁至 `data/`（旧根目录文件启动时自动迁移）；
- 登录锁定可后台手动解封：用户管理后台展示锁定状态（登录失败锁定），并支持一键**解封**（`POST /api/user_manage/unlock`）——清除该用户全部维度（IP+用户名 / 仅用户名）的锁定记录，无需等待锁定期满即可立即登录；
- 补上了插件包的完整性校验与签名、Factory Reset、备份/恢复、启动自检，以及一套 497 项的回归测试和 GitHub Actions CI。

坦白说，这框架远谈不上"完善"。它更多是"自娱自乐"的产物：站在 Flask、APScheduler、Werkzeug 这些巨人的肩膀上，把我需要的那部分想法落了地。也因此，它的安全模型是朴素直接的——**安装插件即信任其作者**。所以它更适合自己的电脑或可信局域网，而不是对外开放的生产环境。

我坚持的原则只有一个：**需求导向，怎么方便怎么来**。所以最终呈现给你的，是一个开箱即用、低门槛、能随手往里加工具、且数据始终在自己手里的工具箱。

## 它是什么

基于 Flask 的插件化**框架**（自托管运行时）：

- **后端插件（Python）**与**前端工具（HTML 包）**都可动态安装 / 更新 / 卸载 / 启用 / 禁用；
- 鉴权是**可选插件**——不装就是游客模式，装了立刻有登录 / 权限控制；
- 文件监听热重载，改完即生效；
- 自带管理后台（仪表盘 / 插件管理 / 日志 / 统计 / 系统重置）。

一句话：这是一个**插件化框架**——给你的本地小程序一个统一的家，以及一套不用重写的"地基"。

## 快速开始

```bash
pip install -r requirements.txt
python app.py
```

浏览器打开 `http://127.0.0.1:5000` 即可（默认仅本机访问；如要局域网使用，设环境变量 `FLASKTOOLKIT_HOST=0.0.0.0`，见下方说明）。

首次运行建议安装内置 `auth` 插件以获得鉴权能力，默认管理员账号 `admin / admin123`（可在 `plugins/configs/auth.json` 修改）。

想马上感受"装插件"的乐趣？安装官方示例：

```bash
pip install -r requirements.txt -r requirements-dev.txt   # install_all.py 依赖 requests
python examples/install_all.py                            # 一键安装 6 个官方示例
```

### 运行环境变量

| 变量 | 默认值 | 说明 |
|------|-------|------|
| `FLASKTOOLKIT_HOST` | `127.0.0.1` | 绑定地址；默认仅本机，局域网访问设 `0.0.0.0` |
| `FLASKTOOLKIT_PORT` | 自动探测 | 显式指定端口；被占用时自动回落 |
| `FLASKTOOLKIT_DEBUG` | 关闭 | 调试模式，生产环境请勿开启 |

## 官方示例

[`examples/`](examples/README.md) 随仓库分发一套可一键安装的示例，完整展示框架能力，也是新插件开发的起始模板：

| 示例 | 类型 | 展示能力 |
|------|------|---------|
| `hello_plugin` | 后端插件 | 生命周期钩子、三层权限、配置读写、自定义页面 |
| `scheduler_demo` | 后端插件 | APScheduler 定时任务（interval/cron） |
| `async_file_demo` | 后端插件 | 文件上传限制、异步任务、状态轮询、结果下载 |
| `dependent_demo` | 后端插件 | 插件依赖声明、跨插件调用 |
| `multitool_demo` | 后端插件 | 大插件多模板：多模板页面路由、辅助 .py、静态资源 |
| `dashboard_demo` | 前端工具包 | 管理员权限、调用后端 API、ECharts 图表、静态资源 |

详见 [examples/README.md](examples/README.md)。

## 文档

详细规格都在 [Flask 插件框架开发规范](documents/Flask插件框架开发规范-v4.0.md)（插件开发、权限模型、前端工具规范、插件包格式、安全设计、运维工具）：

- [官方示例说明](examples/README.md)
- [Flask 插件框架 Roadmap](documents/Flask插件框架-Roadmap-v4.1.md)
- [版本收尾 checklist](documents/版本收尾-checklist.md)
- [GitHub Actions 上手与开源发布指南](documents/GitHub-Actions-上手与开源发布指南.md)

## 测试与 CI

`tests/` 22 个脚本共 497 项回归测试（隔离目录模式，不污染项目文件）；GitHub Actions 在 Python 3.10 / 3.11 / 3.12 上自动执行，覆盖权限、插件包 / 前端工具链路、完整性签名、卸载清单、Factory Reset、大插件多模板页面路由、文件传输（上传限制 / 中文名下载 / Range）、插件静态安全扫描、能力声明交叉校验、运行时审计钩子、运维工具等。

<details>
<summary>展开：19 个测试脚本</summary>

```bash
cd FlaskToolkit
python tests/test_permission.py            # 权限体系 20 项
python tests/test_stage2.py                # 安全加固回归 19 项
python tests/test_zip_slip.py              # 插件包 zip slip 19 项
python tests/test_pack_meta.py             # 插件包描述一致性 17 项
python tests/test_reload_race.py           # 热加载重载竞态 1 项（20 轮）
python tests/test_meta_e2e.py              # 插件包元信息端到端 10 项
python tests/test_frontend_zip_slip.py     # 前端工具 zip slip 21 项
python tests/test_frontend_chain.py        # 前端工具链路端到端 23 项
python tests/test_admin_api.py             # 管理端 API 21 项
python tests/test_factory_reset.py         # Factory Reset 范围 37 项
python tests/test_error_pages.py           # 错误码页面 12 项
python tests/test_package_sign.py          # 完整性校验/签名 22 项
python tests/test_plugin_cleanup.py        # 插件卸载 installed_files 清单 23 项
python tests/test_frontend_permission.py   # 前端工具访问控制 25 项
python tests/test_tools_ops.py             # 运维工具 backup/reset/config 19 项
python tests/test_page_router.py           # 大插件多模板页面路由 + 纯 API 无 name 插件调试页回归 21 项
python tests/test_framework_fixes.py       # 框架小修复：public_page 豁免 + CSRF 单值注入 9 项
python tests/test_file_transfer.py         # 文件传输：全局 413 / 插件级与 route 级上传上限 / 中文名下载 / 下载统计 / Range / on_ready 顺序 12 项
# 合计 22 个脚本 497 项
```

</details>

## 已知局限

- **安全模型为"安装插件即信任其作者"**：插件可执行任意代码，请只安装可信来源的插件。
- 框架更偏向"自娱自乐"的实用工具，未针对公网对抗性环境加固，**不建议部署到对外生产环境**。
- 如需局域网使用，可设 `FLASKTOOLKIT_HOST=0.0.0.0`，但请配合 `auth` 鉴权并自行评估风险。

## 许可与贡献

MIT License · 贡献指南见 [CONTRIBUTING.md](CONTRIBUTING.md) · 开发过程中使用了 AI 辅助编程，约定见下文声明。

### 人工智能辅助开发声明

本项目在开发过程中使用了 AI 辅助编程工具，包括但不限于：代码生成与重构、代码审查、测试用例编写、文档撰写。所有 AI 辅助生成或修改的内容，均已由开发者人工审查，并通过项目自身的回归测试套件（`tests/`，497 项）与启动完整性自检验证后才会合入。

对贡献者的透明性约定：

- 使用 AI 辅助工具是被允许的，但请对提交代码的**正确性、安全性、合规性**负全责。
- AI 生成的代码必须通过项目的回归测试与代码审查（流程见 `CONTRIBUTING.md`）。
- 若 PR 中大量使用 AI 生成内容，建议在 PR 描述中注明，便于维护者审阅。

## Star History

用 [Star History](https://www.star-history.com/?repos=ReconLeo%2FFlaskToolkit&type=date&legend=top-left) 记录本项目的成长历程。

<a href="https://www.star-history.com/?repos=ReconLeo%2FFlaskToolkit&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=ReconLeo/FlaskToolkit&type=date&theme=dark&legend=top-left&sealed_token=6DvZLa9sIvE1KVbLXbIdgQXFE-1hZ_BUK3nyhvtBdgg9TJIBWUD7X5e7VJa30UFnoIUGHciUofZ_Uu8rRfwUbJI_JFPNcma79J0rlrHUOPVqSr4u_4KItnn5bQPeSiWWr2kC6WYkRO63hCndr-wiCz8ie9PIvzXqZiX21cg8T1-Z9PzDSAoMzqFROHAP" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=ReconLeo/FlaskToolkit&type=date&legend=top-left&sealed_token=6DvZLa9sIvE1KVbLXbIdgQXFE-1hZ_BUK3nyhvtBdgg9TJIBWUD7X5e7VJa30UFnoIUGHciUofZ_Uu8rRfwUbJI_JFPNcma79J0rlrHUOPVqSr4u_4KItnn5bQPeSiWWr2kC6WYkRO63hCndr-wiCz8ie9PIvzXqZiX21cg8T1-Z9PzDSAoMzqFROHAP" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=ReconLeo/FlaskToolkit&type=date&legend=top-left&sealed_token=6DvZLa9sIvE1KVbLXbIdgQXFE-1hZ_BUK3nyhvtBdgg9TJIBWUD7X5e7VJa30UFnoIUGHciUofZ_Uu8rRfwUbJI_JFPNcma79J0rlrHUOPVqSr4u_4KItnn5bQPeSiWWr2kC6WYkRO63hCndr-wiCz8ie9PIvzXqZiX21cg8T1-Z9PzDSAoMzqFROHAP" />
 </picture>
</a>
