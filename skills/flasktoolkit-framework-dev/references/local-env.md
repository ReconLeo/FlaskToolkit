# Python 解释器隔离与环境体检（通用）

本页给出**通用**的「解释器/环境把工具链搅坏」识别与规避方法，适用于任何开发机与任何操作系统。
某台具体机器的实例记录**不属于技能内容**，见仓库 `skills/DEV-ENVIRONMENT-NOTES.md`（可选参考，非技能依赖）。

当打包 / 写法体检 / 启动服务 / 全量回归出现**看起来像项目缺陷、实际只在你这台机器复现**的报错时，先看本页。

## 常见症状（三类）

1. **解释器指向非预期环境**：`PYTHONHOME` / `PYTHONPATH` 被 IDE 托管的 venv、发行版封装、企业安全外壳或 Python 环境管理器改写，`python` 实际解析到另一个解释器（缺依赖、版本不符、路径怪异）。
2. **环境注入了审计钩子或改写系统调用**：该环境的 `sitecustomize.py` / `usercustomize.py` 通过 `sys.addaudithook` 拦截或改写 `os.remove` / `os.rmtree`（例如改成「移进回收站」或直接拒绝）。典型表现：
   - 删除类断言失败、插件更新/卸载链路返回 500、临时文件清理不生效；
   - `py_compile` / `__pycache__` 写入报错，连带打包与启动自检失败。
3. **精简/嵌入版解释器缺标准库组件**：没有 `venv` / `ensurepip` / `ssl` / `tkinter`，导致启动、证书、桌面启动器相关用例失败。

## 三步定位（通用命令）

```bash
# ① 我现在用的是哪个解释器
python -c "import sys; print(sys.executable); print(sys.prefix, '|', sys.base_prefix)"

# ② 环境里有没有被注入 sitecustomize/usercustomize
python -c "import sitecustomize, inspect; print(inspect.getsourcefile(sitecustomize))"

# ③ 有没有 PYTHON* 变量在改写搜索路径
echo "PYTHONHOME=[$PYTHONHOME] PYTHONPATH=[$PYTHONPATH]"
```

> Windows PowerShell：`$env:PYTHONHOME` / `$env:PYTHONPATH`；`where python` 看解析顺序。
> ③ 输出非空、或 ② 指向项目之外的路径 → 基本可判定为环境问题。

## 规避方法：显式指定解释器 + 清空 PYTHON* 变量

把解释器路径作为**调用参数**传入（不要依赖 `python` 在 PATH 上的解析结果，也不要在脚本里写死某台机器的路径）：

```bash
# 由用户/环境变量提供，脚本只消费
export SYSTEM_PYTHON=/usr/bin/python3        # 例：Windows 可为 C:\Python313\python.exe
env -u PYTHONHOME -u PYTHONPATH "$SYSTEM_PYTHON" tools/run_all_tests.py
env -u PYTHONHOME -u PYTHONPATH "$SYSTEM_PYTHON" tools/release.py build ...
```

清空变量的等价写法：

| Shell | 写法 |
| --- | --- |
| bash / zsh | `env -u PYTHONHOME -u PYTHONPATH <python> ...`，或 `export PYTHONHOME=; export PYTHONPATH=` |
| PowerShell | `$env:PYTHONHOME=""; $env:PYTHONPATH=""; & $env:SYSTEM_PYTHON ...` |
| cmd.exe | `set PYTHONHOME=` + `set PYTHONPATH=` 后调用 |

## 判定准则（避免误报项目缺陷）

- 换「干净解释器 + 清空 PYTHON*」后报错消失 → **环境问题**，不要为了兼容它去改框架代码；
- 换后仍复现 → 才按项目缺陷走正常排查（最小复现 → 回归断言 → 协调清单）。

## 应用场景

- 全量回归（[testing.md](testing.md)）。
- 打包：runtime 包 / 插件包（[packaging.md](packaging.md)）。
- Python 3.10 语法体检（`ast.parse(..., feature_version=(3, 10))`，见 [testing.md](testing.md)）。
- 启动服务做端到端验证。
- 隔离副本内操作（[framework-copy.md](framework-copy.md)）。

## 补充

- `tools/run_all_tests.py` 会给子进程注入 `PYTHONIOENCODING=utf-8`，Windows 控制台乱码不需要用户额外处理。
- 需要长期固定解释器时，用环境变量（如 `SYSTEM_PYTHON`）或调用方参数传递，**不要在框架源码/脚本里写死绝对路径**。
