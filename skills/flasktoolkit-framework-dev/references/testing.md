# 测试与回归

本页覆盖主框架修改后的回归验证与 CI 同步。任何代码改动后都应走回归；新增测试脚本必须同步进 CI。

## 全量回归

在框架根执行：
```
python tools/run_all_tests.py
```
- 串行遍历 `tests/test_*.py`（当前 **49 脚本**），汇总通过/失败/超时/耗时，退出码 0=全过。
- 常用参数：`-p theme`（只跑文件名含 theme）、`-t 300`（单测试超时秒数）、`--list`（仅列出不执行）、`-v`（失败打印完整日志）、`--keep`（保留历史日志）。
- 日志默认到 `temp/regress/`。
- 测试脚本均自包含（隔离目录），以当前 Python 解释器直接运行。
- 注意：本机需用系统 Python 并清空 PYTHON* 变量执行（见 [local-env.md](local-env.md)）。

## 新增测试脚本必须同步进 CI

新增 `tests/test_*.py` 后，必须把它加进 `.github/workflows/ci.yml` 的 **TESTS 数组**（当前 49 个，勿漏）。漏加会导致 CI 不覆盖新脚本（假绿）。

**测试清单四端点同步**（历次漏过 v4.8.0 的 test_update_checker 未入四处）：
1. `.github/workflows/ci.yml` TESTS 数组与注释脚本数
2. `README.md` 折叠测试列表（条目 + `<summary>` 标题数字）
3. `README.zh-CN.md` 折叠测试列表（同上）
4. `documents/Flask-Plugin-Framework-Dev-Guide-v4.md` 十二章表格行 + 运行命令列表 + `合计 N 个脚本 M 项` 数字

## Python 3.10 语法体检

用系统 Python 对全项目 .py 做语法体检（v4.9.2 教训：f-string 嵌套同引号为 PEP 701 仅 3.12+，本地 3.12 不暴露）：
```python
# 对每个 .py 执行
ast.parse(src, feature_version=(3, 10))
```
注意 f-string 内 `_tr()("...")` 嵌套双引号写法。要求全项目 .py 扫描零错误。

## 其它验证项

- **前端工具真实 HTTP 端到端**：`tests/verify_frontend_chain.py` + `tests/ci_prepare_frontend_demo.py`（上传/更新/卸载链路）；路径随框架演进同步（`frontend_tools.json` 在 `data/` 下，非项目根）。
- **示例打包校验**：`python examples/install_all.py --pack-only`。
- **启动自检**：`python tools/selfcheck.py`（或等价）通过。
- **专项测试**：新增功能应有对应专项测试（如 test_capabilities / test_security / test_page_router）。
- 冒烟验证新功能端到端（必要时 `app.test_request_context` / `test_client`）。

## 运行注意（解释器与环境）

- 回归/体检/启动服务前，先确认 `python` 指向的是**干净解释器**（IDE 托管的 venv、企业安全外壳或环境管理器注入的 `sitecustomize` 审计钩子会让你看到"项目缺陷"假象：删除被拦、`py_compile` 报错、更新/卸载链路 500）。
- 规避方式：解释器路径由调用方提供（如 `SYSTEM_PYTHON`），执行前清空 `PYTHONHOME` / `PYTHONPATH`。
- 三步定位法与判定准则见 [local-env.md](local-env.md)（通用）；具体机器实例另见仓库 `skills/DEV-ENVIRONMENT-NOTES.md`（非技能依赖）。
