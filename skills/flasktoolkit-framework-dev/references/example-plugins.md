# 示例插件开发 / 升级

本页覆盖 `{FRAMEWORK_ROOT}/examples/plugins/<name>/` 下**官方示例插件**的开发、升级、打包与框架同步。补充知识来源：`documents/Flask-Plugin-Framework-Dev-Guide-v4.md` 五、后端插件开发规范。

## 标准插件包结构

```
examples/plugins/<name>/
├── plugin.json          # 描述文件（元信息/权限/依赖/require 版本）
├── <name>.py            # 主插件类（继承 BasePlugin）
├── 可选辅助模块 .py
├── templates/           # 插件模板（<name>.html 等）
└── 可选 static/ 或 locales/   # 静态资源 / 插件语言包
```

打包命令（在框架根执行，源目录需干净、LF）：
```
python tools/package.py pack examples/plugins/<name> -o out.zip --type backend
```
v4.21.1 起 `tools/package.py` 已用统一 `PACK_SKIP_DIRS` 排除 `__pycache__/.pyc/.pyo`，无需手动清 pyc。

## 字段两处一致（铁律）

`plugin.json` 与主 `.py` 类属性**两处必须一致**，冲突字段会导致安装 400：

- `name`、`version`、`title`、`description`、`author`、`category`、`permission`、`dependencies`、`require_framework_version`

升级示例插件时逐字段核对两处。

## 关键版本/能力约束

- `require_framework_version` **≤ 当前框架版本**才能安装；用新版能力（如 `get_data_path`）须要求 ≥ 该能力引入版本。
- `capabilities` 声明与实际行为匹配（如 `scheduler`）；自属路径读写隐式豁免无需声明。
- **内容变更须同步升级 `version`**（保证 update 可重复安装）。
- 打包产物 + 插件内 manifest/README/en.json 保持 LF。

## 示例集整体同步

升级任一示例插件后，逐项核对：
- `examples/manifest.json`：`name`/`title`/`path`/`type`/`focus` 描述无过时信息。
- `examples/README.md`：示例表描述同步。
- `examples/install_all.py --pack-only`：打包校验通过。
- `documents/Flask-Plugin-Framework-Dev-Guide-v4.md`：对应章节（5.x 规范）若有示例引用同步。

## 打包/安装验证

- 用 `python examples/install_all.py --pack-only` 做示例集打包校验。
- 需要真实环境验证时，参照 [framework-copy.md](framework-copy.md) 在隔离副本内安装测试，**不在主框架运行时内随意安装卸载**。

## 本机执行注意

打包/语法检查/启动服务使用系统 Python 并清空 PYTHON* 变量，见 [local-env.md](local-env.md)。
