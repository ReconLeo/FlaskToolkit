# 框架协调清单 · 待修复 Backlog

> 作用：**收集外部插件开发者的协调清单发现与自己实测的问题，攒批修复**。
> 未修复项在此登记（现象 / 根因 / 规避 / 建议修复 / 来源）；修复后从本表移除，并在
> `Flask-Plugin-Framework-Changelog.md` 对应版本小节留下记录。
> 已修复的历史清单（KaleidoMini FTK-KM-*、xfime_iat FTK-XI-*）可在对应版本小节与
> `skills/flasktoolkit-subproject-dev/references/known-framework-issues.md` 中查到。

## 待修复（按批处理，不强求逐条即刻修）

| 编号 | 标题 | 级别 | 来源 | 状态 |
|---|---|---|---|---|
| FTK-BL-01 | 插件 `.py` 带 UTF-8 BOM → 被判 `syntax` high 且**无逃生舱**，enforce 下 100% 拒装 | 中（误伤，可规避） | 自测（v4.23.5 发版验证发布产物时发现） | 待修复 |
| FTK-BL-02 | `plugins/temp/<name>/` 无自动过期清理（上传临时文件只增不减） | 低（磁盘累积） | 子插件开发反馈（known-framework-issues B2） | 待修复 |
| FTK-BL-03 | 框架无全局上传大小上限（仅靠插件自校验 + `MAX_CONTENT_LENGTH` 默认值） | 低（观察点） | 子插件开发反馈（known-framework-issues B3） | 待修复 |

## FTK-BL-01：BOM 导致静态扫描误判 syntax，且 `# scan:ignore` 无效

**现象**

```
[HIGH  ] plugin_x.py:1 syntax — 源码无法解析（可能混淆/加密）：invalid non-printable character U+FEFF (<unknown>, line 1)
结论: 存在不可豁免的高风险行为…（enforce 模式将拒绝安装）
```

- 插件文件存成**带 BOM 的 UTF-8**（Windows 记事本 / PowerShell 5.1 `Set-Content -Encoding UTF8` 默认行为）即触发；
- 该 finding **不可豁免**：`scan_code()` 在 `ast.parse` 失败分支 `return report`，而 `# scan:ignore` 的过滤循环在函数末尾 → 语法类 finding 永远不参与忽略；
- 但 Python 自身**容忍 BOM**（`compile(open(p,'rb').read())` 实测正常、插件可正常导入）→ 纯属误伤，且 enforce 下无任何安装通路（除改为无 BOM）。

**根因**

`core/plugin_scanner.py::scan_file` 用 `encoding='utf-8'` 读、`scan_plugin_zip` 用 `bytes.decode('utf-8')`，BOM 作为 `U+FEFF` 保留在源码首字符；`ast.parse` 报
`SyntaxError: invalid non-printable character U+FEFF` → 落 `_add(report, 'high', 'syntax', ...)`。

**规避（插件侧，已知可行）**

- 源文件存为**无 BOM 的 UTF-8**：VS Code「Save with Encoding: UTF-8」；
- PowerShell：`[System.IO.File]::WriteAllText($p, $s, (New-Object System.Text.UTF8Encoding($false)))`，PS7 用 `-Encoding utf8NoBOM`；
- 仓库层加 BOM 检查（`git grep -Il $'\xEF\xBB\xBF'` 或 pre-commit hook），`.gitattributes` 只能规范行尾、不处理 BOM。

**建议修复**

1. 读源码统一 `utf-8-sig`（`scan_file` / `scan_plugin_zip`，前端 `scan_frontend_zip` 同理）——一行改动，BOM 前缀被剥离后正常解析；
2. 兜底可诊断性：`syntax` 分支若源码仅以 `\ufeff` 开头且剥掉后可解析，直接给"文件为带 BOM 的 UTF-8，请另存为无 BOM"的定向提示，而不是报"可能混淆/加密"；
3. 顺带覆盖 v4.23.1 的同类教训（配置读取已统一 `utf-8-sig`，此处是遗留的同源位置）。

## 攒批约定

- 新增发现：在本表加一行 + 补一节（现象 / 根因 / 规避 / 建议修复 / 来源），级别按"是否会阻断安装/运行"判定（阻断=中起）；
- 每批修复：优先取**误伤类**（阻断合法工作流）与**低成本高收益**项；修完从本表移除并写入 changelog；
- 外部报告（issue / 协调清单）修复后仍需回帖说明，便于报告者撤回插件侧 workaround。
