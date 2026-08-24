# 参与贡献指南（Contributing Guide）

欢迎为 **FlaskToolkit**（基于 Flask 的插件化全栈工具集）贡献代码、文档、测试或反馈问题。
在提交贡献前，请阅读本指南与《[Flask插件框架开发规范](documents/Flask插件框架开发规范-v4.0.md)》。

## 一、环境准备

```bash
# 1. 克隆项目
git clone https://github.com/<你的账号>/FlaskToolkit.git
cd FlaskToolkit

# 2. 安装依赖（建议使用虚拟环境）
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt

# 3. 启动服务验证
python app.py                    # 访问 http://127.0.0.1:5000，默认管理员 admin / admin123
```

## 二、运行测试

回归测试套件位于项目 `tests/` 目录，共 12 个脚本、222 项：

```bash
cd FlaskToolkit
for t in tests/test_*.py; do python "$t"; done   # 全部
python tests/test_permission.py                  # 单个（权限体系）
python core/selfcheck.py                         # 框架完整性自检
```

**提交 PR 前请确保全部测试通过。** 注意测试会读写真实项目状态（auth.json / sessions 等），
CI 环境会在每个测试后自动清理（`tests/ci_cleanup.py`），本地请手动清理或容忍污染。

## 三、提交 Issue

- 先搜索是否已有相似 Issue，避免重复。
- 标题简述问题（如"插件上传超 10MB 时报错信息不友好"）。
- 内容尽量包含：
  - 复现步骤、期望行为、实际行为；
  - 运行环境（操作系统、Python 版本、FlaskToolkit 版本）；
  - 相关日志（`logs/`）或报错堆栈。

## 四、提交 Pull Request（PR）

1. **Fork** 本仓库到你的账号。
2. Clone 你的 fork，创建新分支（功能/修复命名清晰）：
   ```bash
   git checkout -b feat/add-xxx      # 或 fix/xxx
   ```
3. 修改代码，**遵循开发规范**（模块职责、命名、注释、权限装饰器声明等）。
4. 新增功能请**同步补充/更新回归测试**（`tests/`）与文档（`documents/`、`README.md`）。
5. 本地跑通全部测试（见第二节）。
6. 提交并推送：
   ```bash
   git add -A
   git commit -m "feat: 描述改动（参考 Conventional Commits 风格）"
   git push origin feat/add-xxx
   ```
7. 在 GitHub 上对上游仓库发起 **Pull Request**，描述改动内容与验证结果。
8. **CI 会自动运行**（GitHub Actions）：PR 会在多版本 Python 上跑完整回归套件，
   请等待检查结果；如有失败，根据日志修复后重新推送。

## 五、PR 合并约定

- 保持 PR 聚焦：一个 PR 只解决一个问题。
- 不要在主分支直接提交，所有改动经 PR 合并。
- 提交信息风格建议：`feat:` / `fix:` / `docs:` / `test:` / `refactor:` / `chore:`。

## 六、开源规范

- 本项目采用 **MIT License**（见 `LICENSE`）。
- 敏感信息（密码、密钥、token、个人数据）**严禁**提交到仓库。
- 提交前运行 `git status` 确认没有误提交运行时数据（已被 `.gitignore` 覆盖：`data/`、`logs/`、`temp/` 等）。

感谢你的贡献！
