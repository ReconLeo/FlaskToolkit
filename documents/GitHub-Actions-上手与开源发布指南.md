# GitHub Actions 上手与开源发布指南

> 面向首次接触 GitHub Actions 的开发者。本文档介绍本项目已配置的 CI 工作流，以及
> 如何把 FlaskToolkit 发布到 GitHub 开源、贡献代码的完整操作步骤。

---

## 一、GitHub Actions 是什么？

GitHub Actions 是 GitHub 内置的**持续集成 / 持续交付（CI/CD）**平台：
- 仓库中放置 `.github/workflows/*.yml` 工作流文件，GitHub 会在满足**触发条件**时自动在云端执行其中定义的步骤（安装依赖、跑测试、构建等）。
- 每次执行称为一次 **Workflow Run**，由若干 **Job**（作业）组成，Job 内是顺序执行的 **Step**（步骤）。
- 每个 Job 在**独立的云端虚拟机（runner）**上运行（本项目用 `ubuntu-latest`），因此环境和仓库代码每次都是全新的，互不污染。
- 免费额度：公开仓库免费且不限时长；私有仓库有每月免费额度。

本项目工作流文件：[.github/workflows/ci.yml](../.github/workflows/ci.yml)

## 二、本项目 CI 做了什么？

| 触发条件 | push 到 `main`/`master`、任何 PR、手动触发（workflow_dispatch） |
|---------|----------------------------|
| 运行环境 | `ubuntu-latest` × Python **3.10 / 3.11 / 3.12**（矩阵并行） |
| 步骤 | ① 检出代码 → ② 设置 Python → ③ 安装依赖 → ④ 语法编译检查 → ⑤ 框架完整性自检 → ⑥ 配置/工具 CLI 冒烟 → ⑦ 运行 **12 个回归测试（222 项）**，测试间自动清理 → ⑧ 打包/签名工具端到端 → ⑨ 失败时上传日志 |
| 通过标准 | 所有 Job、所有步骤全部成功（绿色 ✅） |

每个 PR 与 push 都会自动验证代码在多版本 Python 下可安装、可启动、全部测试通过，
**在合并前就把问题挡在门外**。

## 三、首次发布到 GitHub：完整操作步骤

### 第 1 步：创建 GitHub 仓库

1. 登录 GitHub → 右上角 **+** → **New repository**。
2. Repository name：填 `FlaskToolkit`（可自定义）。
3. 可见性：选 **Public**（开源）或 Private（私有，CI 同样可用）。
4. **不要**勾选 "Add a README / .gitignore / license"（本地已有，避免冲突）。
5. 点击 **Create repository**。

### 第 2 步：本地初始化为 git 仓库并推送

在项目根目录打开终端（Git Bash / Terminal）：

```bash
cd C:/Users/Admin/Desktop/FlaskToolkit

# 1. 初始化 git 仓库（若尚未初始化）
git init

# 2. 设置提交者信息（全局一次即可；GitHub 统计贡献需要邮箱）
git config --global user.name  "你的名字"
git config --global user.email "你的邮箱（GitHub 已验证邮箱）"

# 3. 添加远程仓库（把 <你的账号> 替换为真实账号）
git remote add origin https://github.com/<你的账号>/FlaskToolkit.git

# 4. 暂存并提交（.gitignore 已排除 data/logs/temp 等运行时文件）
git add -A
git commit -m "feat: FlaskToolkit 插件化全栈工具集 v4.1（含 CI 与开发运维工具）"

# 5. 推送到 GitHub（首次会要求输入账号密码，或弹窗授权）
git branch -M main
git push -u origin main
```

> 若本地未安装 git，可到 https://git-scm.com 下载；Windows 可参考 Git Bash 使用。

### 第 3 步：查看 CI 自动运行结果

1. 推送完成后，打开仓库页面 → 顶部 **Actions** 标签。
2. 会看到一条正在运行的 workflow（图标转圈）。
3. 点击它 → 左侧有 `回归测试（Python 3.10/3.11/3.12）` 三个 Job → 点击展开查看每个 Step 的日志。
4. 全部绿色 ✅ 表示通过；红色 ❌ 表示失败，点击失败 Step 展开日志定位原因。
5. 失败时会自动生成 **Artifacts（日志包）**，可在 Job 页面底部下载排查。

### 第 4 步：手动触发

需要再次运行（不改代码）时：仓库 **Actions** 标签 → 左侧选 `CI` → 右侧 **Run workflow** 按钮 → 选分支 → Run。

## 四、常见问题排查

| 现象 | 原因 / 解决 |
|------|-----------|
| push 被拒绝（non-fast-forward） | 远程有新提交，先 `git pull --rebase origin main` 再 push |
| Actions 标签下没有工作流 | 检查 `.github/workflows/ci.yml` 是否已提交（`git ls-files .github`）；触发条件是否匹配（分支名/PR） |
| Job 未运行（跳过） | 触发条件不满足，如 push 到非 main/master 分支（不触发 push，但 PR 会触发） |
| 依赖安装失败 | 多为网络问题，重试；或检查 requirements 是否可安装 |
| 测试失败 | 展开日志定位失败的测试；本地先 `python tests/<脚本>.py` 复现修复后再推送 |
| 需要更多运行时间 | 免费额度内正常；如需限制版本可删除 strategy 中的部分 python-version |

## 五、贡献开源社区：Fork → PR 流程

**方式一：直接对他人项目提 PR（协作开发）**

1. 打开目标仓库 → 右上角 **Fork**（复制到你的账号）。
2. 克隆你的 fork：`git clone https://github.com/<你的账号>/FlaskToolkit.git`
3. 创建功能分支：`git checkout -b feat/add-xxx`
4. 修改代码 → 本地跑通全部测试（见 CONTRIBUTING.md 第二节）。
5. 推送：`git push origin feat/add-xxx`
6. 回到**原仓库** → **Pull requests** → **New pull request** → 选择你的分支 → 创建 PR。
7. 等待维护者 review，或 CI 自动检查；有反馈则继续提交（自动更新 PR）。

**方式二：他人向你提 PR（你是维护者）**

- 在仓库 **Pull requests** 标签查看 PR → 查看改动（Files changed）→ 运行 CI 检查 → 有疑问留言 → 通过后 **Merge pull request**。

**提 Issue（报告问题 / 建议）**

- 仓库 **Issues** → **New issue** → 按 CONTRIBUTING.md 第三节填写（复现步骤、环境、日志）。

## 六、已就绪的开源配套

| 文件 | 用途 |
|------|------|
| `.github/workflows/ci.yml` | CI 工作流（多版本 Python 全量回归） |
| `LICENSE` | MIT 开源许可 |
| `.gitignore` | 排除运行时数据（data/logs/temp/备份等） |
| `CONTRIBUTING.md` | 贡献指南（环境、测试、Issue、PR 流程） |
| `README.md` | 项目说明与快速开始（英文版） |
| `README.zh-CN.md` | 项目说明与快速开始（中文版） |
| `tests/` | 16 个回归测试脚本（310 项）+ `ci_cleanup.py` |
| `documents/` | 开发规范（v4.0）+ Roadmap + 本指南 |

发布到 GitHub 后，只需把仓库地址分享出去，别人就能 clone、提 Issue、提 PR，CI 会自动守护代码质量。
