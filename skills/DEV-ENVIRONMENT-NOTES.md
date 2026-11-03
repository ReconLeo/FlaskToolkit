# 开发机环境实例记录（非技能依赖）

> **定位**：本文件记录**某一台具体开发机**上遇到过的环境陷阱与当时的规避命令，供其它机器遇到**类似症状**时对照参考。
> 它**不属于**任何技能的指令内容——技能本体（`flasktoolkit-framework-dev/`、`flasktoolkit-subproject-dev/`）刻意不含机器专属信息。
> 通用排查方法请看 `flasktoolkit-framework-dev/references/local-env.md`；本文件只是"实例"，不构成依赖。

## 实例 1：Windows 开发机上的 Python 环境托管（2026-11 记录）

| 项 | 记录 |
| --- | --- |
| 平台 | Windows 11 + PowerShell |
| 现象 | 环境变量 `PYTHONHOME` / `PYTHONPATH` 指向一个 Python 环境管理器（"灵犀 python-env"）的目录；该环境的 `sitecustomize.py` 注册了审计钩子，**拦截 `os.remove` / `os.rmtree` 等永久删除**（改为引导回收站，或直接拒绝），并使 `py_compile` 启动报错 |
| 连带症状 | 真实 HTTP 回归测试的"更新清理/卸载"环节返回 500；`python app.py` 启动自检必失败；打包脚本里 `__pycache__` 清理静默失败 |
| 当时采用的干净解释器 | `D:\anaconda3\python.exe`（系统级 Anaconda），并清空两个变量 |
| 当时的规避命令 | PowerShell：`$env:PYTHONHOME=""; $env:PYTHONPATH=""; & "D:\anaconda3\python.exe" tools\run_all_tests.py`<br>bash：`env -u PYTHONHOME -u PYTHONPATH "D:/anaconda3/python.exe" tools/run_all_tests.py` |
| 如何确认 | `python -c "import sys; print(sys.executable)"` 指向环境管理器目录；`python -c "import sitecustomize, inspect; print(inspect.getsourcefile(sitecustomize))"` 指向该环境而非项目 |

## 使用建议

- **不要**把上面这些路径抄进技能或脚本——用 `SYSTEM_PYTHON` 等环境变量传入（技能内 `references/local-env.md` 与 `scripts/pack_plugin.sh` 都按此约定）。
- 若你的机器出现同族症状（删除被拦、`py_compile` 报错、解释器指向奇怪目录），先跑 `local-env.md` 的"三步定位"，再对照本实例决定用哪个干净解释器。
- 换干净解释器后症状消失 = 环境问题，**不要**为了兼容它去改框架代码。
