# 版本发布收尾

本页覆盖 FlaskToolkit 版本发布完整流程。**发布前必须先过版本治理门禁；未经用户明确指示不得发布、不得打 tag、不得提升/改写版本号。** 权威清单见 `{FRAMEWORK_ROOT}/documents/Release-Wrapup-Checklist.md`（10 类检查点）。

## 发布准入（Definition of Done，缺一不发）

1. **无未决 P0/P1**：修复批次收口时 P0/P1 清零，P2 可下推。
2. **全量回归 + CI**：本地 47 脚本全过 + GitHub Actions CI 全绿；新增脚本须同步进 ci.yml TESTS 数组。
3. **打包端到端验证**：release 产物下载 → sha256 比对 → 干净环境安装跑一遍。

**版本纪律（双轨）**：修复累计到稳定线单版本低频发布；新功能走特性线攒够主题再整合发布，绝不夹带进修复批次。**未经用户明确指示不得发布。**

## 发布步骤（v4.9.2 起固化的完整流程）

1. **功能/修复合入** → 全量回归（[testing.md](testing.md)）+ CI 通过。核查 ci.yml：新增测试脚本同步进 TESTS 数组；前端工具端到端 step 保留可用。
2. **版本号五端点同步**：`global_var.FRAMEWORK_VERSION` + `tests/test_admin_api.py` 断言 + README 双版徽章 + `SYSTEM_VERSION_LABEL` + `core/framework_manifest.py` 核对。用 `python tools/release.py bump --version X.Y.Z` 自动同步三处 + 徽章。
3. **构建 runtime 包**：`python tools/release.py build --version X.Y.Z --changes "..." --changes "..." --download-url "https://github.com/{owner}/{repo}/releases/download/vX.Y.Z/FlaskToolkit-X.Y.Z-runtime.zip"`（拿 sha256 + 重写 changelog.json）。细节见 [packaging.md](packaging.md)。
4. **git commit**（README / changelog.json / 开发规范等）→ `git tag vX.Y.Z` → `git push`（tag 一起 push）。
5. **gh release create** 上传 zip + Release notes。
6. **changelog.json 是强制同步点**：必须随 Release 一起 commit + push（漏则版本数据缺失）。
7. **端到端验证**：`curl raw changelog.json` 返回 200 + `curl -L <release zip>` 下载后 sha256 比对一致。
8. **记忆/知识沉淀**：变更结果回写项目记忆（版本章节 + 历史演进）。

## 版本收尾 checklist 要点

- **版本号五端点**一致（见上）。
- **配置核对**：`CONFIG_ITEMS` 新增项同步到开发规范配置项表。
- **数据路径**：`USER_DATA_PATHS` 单处定义，更新/备份/重置不得破坏用户数据（`data/`、`plugins/data/`、`plugins/configs/`、`logs/`）。
- **测试数字同步**：断言数/脚本数变更须同步到 README 双版 + 开发规范 + CI（tests 数组）。
- **ci.yml 核查**：TESTS 数组与 `tests/test_*.py` 完全一致；端到端 step 保留可用；`verify_*.py` 路径随框架演进同步（frontend_tools.json 在 `data/` 下）。
- **示例同步**：官方示例 `require_framework_version` 等与当前版本对齐（[example-plugins.md](example-plugins.md)）。
- **行尾**：统一 LF，禁止 CRLF/`\r\r\n`（[dev-conventions.md](dev-conventions.md)）。
- **文档双同步**：README 双版 + 开发规范 + `documents/Flask-Plugin-Framework-Changelog.md`（历史演进唯一出处，新增版本小节 + 版本线总览表）。
- **回归与 CI**：全量回归全过。

## 路径不硬编码

- `{GH_EXE}`：gh 位于特定路径（如 `D:\GitHub CLI\gh.exe`），**Git Bash PATH 通常不含，需全路径**；向用户采集，不预设。
- git 操作：`git --version` 确认可用；commit message 惯例 `feat(vX.Y.Z): 摘要`（或 fix 前缀）。
- runtime zip / download-url 的 owner-repo 以用户提供的仓库为准（如 `ReconLeo/FlaskToolkit`），不硬编码。
