# FlaskToolkit v4.23.5

静态扫描门禁的可用性修复：让"调用外部二进制"的插件在 `enforce` 下真正装得上，同时把门禁判定收成一处、把拒绝原因说到能照做。全量回归 49 脚本 0 失败。

## 问题（来自 xfime_iat 子项目上报的协调清单）

`PLUGIN_SCAN_MODE=enforce` 时，任何 `import subprocess` 的插件**永远装不上，且没有任何逃生舱**：

- `# scan:ignore` 对 `import` 类 finding **永久失效**——import finding 的行号被写死为 `0`，而忽略注释是按行号匹配的，写在哪都命中不了；
- 于是"不可约束 high 恒阻断"变成死结：作者只剩两条路——`--no-scan`（**整体跳过扫描**，连 pickle/eval 都不查）或把扫描降级到 `report`（**拖垮全部插件**的保护）。越想用门禁的人越被迫关掉门禁；
- 声明 `capabilities: ["process:exec:ffmpeg"]` 也救不了：安装期只判"有没有 process 域"，与实际执行的二进制无关（而运行期审计钩子是真按 basename 比对的）。

## 修复（Community 定位下的明确规则）

**规则固化**：不可约束 high（eval/exec/compile、pickle/marshal、混淆、动态导入、socket.bind/listen、syntax、subprocess…）**始终保持阻断**，`capabilities` 不能为其背书 —— `# scan:ignore` 是**唯一通路**（enforce 退化为"知情声明防线"：既向使用者告知高危行为，又对恶意插件开发者形成威慑）。归因豁免与 `scan:ignore` 属 Community；动态命令分析、签名者背书属 Enterprise。

1. **import 记录真实行号**：`# scan:ignore` 恢复生效（对 `import` 与调用行各自打一处，通常两行都要标）。
2. **子进程按可执行名归因**：扫描器从 `subprocess.*` / `os.system` / `os.popen` / `os.exec*` / `os.spawn*` 首参静态提取可执行名（字面量取首 token、字面量列表/元组取首元素，basename 小写），与 `process:exec[:<bin>]` 逐一比对（裸 `process:exec` = 任意可执行的粗声明）。**即使该行已 `scan:ignore`，仍须声明匹配的能力**，否则拒绝；**动态构造的命令**（变量/f-string/拼接）无法归因 → 拒绝（把可执行名写成字面量即可；动态分析不在 Community 范围）。
3. **判定收成一处 + 会说人话**：新增 `core/plugin_scanner.evaluate_gate()`，安装 CLI / 服务层 / 上传预览共用；拒绝时逐条给出"文件:行、可执行什么、缺哪条声明、该给哪行加 ignore"。报告与 `tools/scan.py` 直接标 `[已 # scan:ignore 豁免]` / `[可执行 ffmpeg（已归因 process:exec）]` / `[动态构造命令（不可归因）]`。
4. **`install_plugin.py --scan-mode off|report|enforce`**：`--base` 语义不变（只切路径不切配置），新增显式覆盖，并**始终打印生效模式与来源**——隔离测试里"改了隔离运行时的 enforce 却不生效"不再靠猜。
5. **`package.py` 自动创建输出目录**：`pack -o dist/x.zip` 在 `dist/` 不存在时自动建目录（此前抛 `FileNotFoundError` traceback）。
6. **pip 依赖缺失改为醒目警告**：离线 CLI 复用统一的 `check_pip_dependencies`（支持 `name>=x`，修掉误报），以 `[警告]` 输出未就绪原因 + `${python} -m pip install <pkg>`；加载期把"插件依赖"与"pip 依赖"分开告警，并写入后台可读的「未加载原因」。

## 升级提示

- 若你的插件用了 `subprocess`：给 `import subprocess` 行与调用行各加 `# scan:ignore`，并在 `plugin.json` 声明 `process:exec:<实际可执行名>`（例：`process:exec:ffmpeg`）。命令请写成字面量或字面量列表，动态拼接无法归因。
- 脚本化安装/CI：可用 `--scan-mode enforce` 显式指定，输出里会打印"模式 + 来源"。
- 打包脚本：`-o dist/...` 不再需要先 `mkdir dist`。

## 测试与文档

- `test_plugin_scan` 46→64（import 行号与 ignore、归因闸门 12 种组合、动态命令拒绝、报告标记）；`test_capabilities` 73→77（精确 bin 归因/不匹配/缺声明建议/裸声明）；`test_scaffold_tools` 53→61（pack 建目录、`--scan-mode`、pip 警告）。
- 开发规范 10.6 新增「子进程归因闸门」小节，10.7 process 语义、5.6.2.1 依赖报告口径、14.x CLI 说明同步。

**全量回归 49 脚本 0 失败。**

- **Runtime**: `FlaskToolkit-4.23.5-runtime.zip`（精简运行包，115 文件 + `manifest.json`）
- **sha256**: `418c54b0f381da812997e84085441f9c523b93f43d5542a1c6001cc7cc196923`
