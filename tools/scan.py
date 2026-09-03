# -*- coding: utf-8 -*-
"""FlaskToolkit 插件静态扫描 CLI（v4.3.1，安全强化 P1 阶段一）

对插件代码做安装前风险分析：后端插件包（AST 级）与前端工具包（正则级）。
与安装链路使用同一扫描核心（core/plugin_scanner.py），供人工审查 / CI 使用。

用法：
  python tools/scan.py <path>            # 扫描 .py 文件 / 插件包.zip / 前端工具包.zip / 目录（递归 .py）
  python tools/scan.py <path> --json     # 输出 JSON 报告

退出码：0 = 无高风险；1 = 存在高风险（供 CI / 脚本判断）；2 = 参数/IO 错误。
"""
import argparse
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.plugin_scanner import (  # noqa: E402
    scan_file, scan_plugin_zip, scan_frontend_zip, format_report, should_block, _new_report, _merge, _dedupe,
)


def scan_path(path: str) -> dict:
    """按目标类型分派扫描：.py / .zip（按内容判别前后端）/ 目录递归"""
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    if os.path.isfile(path):
        if path.endswith('.py'):
            return scan_file(path)
        if path.endswith('.zip'):
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
            # 前端工具包含 config.json 入口，后端插件包含 plugin.json
            if 'config.json' in names:
                return scan_frontend_zip(path)
            return scan_plugin_zip(path)
        raise ValueError(f'不支持的文件类型: {path}（支持 .py / .zip）')

    # 目录：递归扫描 .py（跳过 __pycache__ / templates / static）
    report = _new_report()
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git')]
        for fn in files:
            if fn.endswith('.py'):
                _merge(report, scan_file(os.path.join(root, fn)))
    return _dedupe(report)


def main():
    ap = argparse.ArgumentParser(description='FlaskToolkit 插件静态扫描 CLI')
    ap.add_argument('path', help='.py 文件 / 插件包.zip / 前端工具包.zip / 目录')
    ap.add_argument('--json', action='store_true', dest='as_json', help='输出 JSON 报告')
    args = ap.parse_args()

    try:
        report = scan_path(args.path)
    except (FileNotFoundError, ValueError, zipfile.BadZipFile) as e:
        print(f'错误: {e}', file=sys.stderr)
        sys.exit(2)

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_report(report, title=f'扫描报告: {args.path}'))

    if should_block(report):
        print('\n结论: 存在高风险行为（enforce 模式将拒绝安装）')
        sys.exit(1)
    print('\n结论: 无高风险行为')


if __name__ == '__main__':
    main()
