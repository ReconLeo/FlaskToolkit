# -*- coding: utf-8 -*-
"""FlaskToolkit 插件手动安装 CLI（v4.10.0 Accessibility，M6）

不运行框架时离线安装插件包（与前端后台 /admin/plugins 上传等效）：
- backend  后端插件包：校验（完整性/描述一致性/框架版本/静态扫描）→ 安全解压到
           plugins/ + templates/plugins/ + 静态资源，落盘 plugins/<name>.json（含 installed_files 清单）
           → 提示缺失的 pip 依赖（pip_dependencies，缺失不阻止安装，启动时跳过加载并告警）
- frontend 前端工具包：校验（完整性/config.json/入口 html/框架版本/静态扫描）→ 安全解压到
           templates/frontend_tools/ → 注册 data/frontend_tools.json
- list     列出当前已安装的插件与前端工具（离线查看）

用法：
  python tools/install_plugin.py backend demo_plugin.zip [--update] [--no-scan]
  python tools/install_plugin.py frontend my_tool.zip [--update] [--no-scan]
  python tools/install_plugin.py list
  # 指定框架根（默认脚本上级目录，即本仓库根）：
  python tools/install_plugin.py backend demo_plugin.zip --base /path/to/FlaskToolkit

说明：
- 安装/更新后插件在下次启动框架时自动加载（本工具不启动服务）。
- 同名插件存在时需 --update（按旧 installed_files 清单清理旧文件后解压新包）；
  --update 仅当包内 plugin.json 版本不低于已装版本时执行。
- 静态扫描默认按 PLUGIN_SCAN_MODE（off/report/enforce）执行；--no-scan 完全跳过。

退出码：0 = 成功；1 = 参数/校验/IO 错误。
"""
import argparse
import importlib.metadata
import json
import logging
import os
import sys
import time
import zipfile

# 安装工具自带进度输出，静默框架 WARNING 级日志（如“未知条目已忽略”），仅保留 ERROR
logging.getLogger('flask.app').setLevel(logging.ERROR)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import global_var  # noqa: E402
from core.plugin_pack import (extract_plugin_pack, parse_plugin_pack,  # noqa: E402
                              compare_versions, check_framework_version)
from core.package_sign import verify_package  # noqa: E402
from routes.frontend import safe_extract_frontend  # noqa: E402
from core.frontend_tools import load_frontend_tools  # noqa: E402
from core.plugin_scanner import scan_plugin_zip, scan_frontend_zip, should_block  # noqa: E402

DEFAULT_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------- 基础 ----------------

def resolve_base(base: str) -> str:
    """指定框架根：--base 或默认脚本上级目录；同步 patch global_var 路径常量"""
    base = os.path.abspath(base or DEFAULT_BASE)
    if not os.path.isdir(os.path.join(base, 'plugins')) or not os.path.isfile(os.path.join(base, 'app.py')):
        raise ValueError(f"不是有效的 FlaskToolkit 框架根（缺少 plugins/ 或 app.py）: {base}")
    overrides = {
        'BASE_DIR': base,
        'UPLOAD_TEMP_DIR': os.path.join(base, 'temp'),
        'STATS_FILE': os.path.join(base, 'data', 'stats.json'),
        'PLUGIN_CONFIGS_DIR': os.path.join(base, 'plugins', 'configs'),
        'FRONTEND_TEMPLATE_DIR': os.path.join(base, 'templates', 'frontend_tools'),
        'FRONTEND_CONFIG_FILE': os.path.join(base, 'data', 'frontend_tools.json'),
    }
    for attr, val in overrides.items():
        setattr(global_var, attr, val)
    return base


def _scan_gate_cli(zip_path: str, kind: str, name: str, no_scan: bool):
    """静态扫描门禁（与框架行为一致：off 跳过 / report 打印摘要 / enforce 高风险拒绝）"""
    if no_scan or global_var.PLUGIN_SCAN_MODE == 'off':
        return
    report = scan_plugin_zip(zip_path) if kind == 'backend' else scan_frontend_zip(zip_path)
    if report['summary']['high'] > 0:
        print(f"[扫描] {name} 发现 {report['summary']['high']} 项高风险行为（report 模式放行）:")
        for item in report['findings'][:10]:
            print(f"       - {item.get('type', '?')}: {item.get('desc', '')}")
        if global_var.PLUGIN_SCAN_MODE == 'enforce' and should_block(report):
            raise ValueError(f"静态扫描存在高风险行为，PLUGIN_SCAN_MODE=enforce 已拒绝安装（--no-scan 可跳过）")
    elif report['summary']['high'] == 0:
        print(f"[扫描] {name} 静态扫描通过（{report['summary'].get('info', 0)} 项提示）")


def _check_pip_dependencies(pip_deps):
    """检测 pip_dependencies 缺失项，返回缺失列表（缺失不阻止安装，启动时框架跳过加载并告警）"""
    missing = []
    for pkg in (pip_deps or []):
        try:
            importlib.metadata.distribution(pkg)
        except importlib.metadata.PackageNotFoundError:
            missing.append(pkg)
    return missing


# ---------------- backend ----------------

def install_backend(args, base: str) -> int:
    pack = os.path.abspath(args.pack)
    if not os.path.isfile(pack):
        print(f"错误：插件包不存在: {pack}", file=sys.stderr)
        return 1
    if not pack.endswith('.zip'):
        print("错误：插件包必须是 .zip 格式", file=sys.stderr)
        return 1

    # 1. 完整性校验（P2-4 方案C：manifest 哈希清单 + 可选签名）
    vres = verify_package(pack, 'backend')
    if not vres['ok']:
        print(f"错误：完整性校验失败: {vres['message']}", file=sys.stderr)
        return 1
    if vres.get('warn_only'):
        print(f"[警告] {vres['message']}")

    # 2. 描述解析 + 一致性对齐校验（含框架最低版本校验）
    desc = parse_plugin_pack(pack)
    name = desc['name']
    version = str(desc.get('version', '1.0.0'))

    # 3. 静态扫描门禁
    _scan_gate_cli(pack, 'backend', name, args.no_scan)

    # 4. 同名与版本检查
    plugin_file = os.path.join(base, 'plugins', f'{name}.py')
    existing_meta = None
    meta_path = os.path.join(base, 'plugins', f'{name}.json')
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                existing_meta = json.load(f)
        except Exception:
            existing_meta = None
    if os.path.exists(plugin_file) or (existing_meta and not args.update):
        if not args.update:
            print(f"错误：插件 {name} 已存在，更新请加 --update（将按旧 installed_files 清单清理后重装）",
                  file=sys.stderr)
            return 1
        if existing_meta:
            old_ver = str(existing_meta.get('version', '0'))
            if compare_versions(version, old_ver) < 0:
                print(f"错误：包版本 {version} 低于已装版本 {old_ver}，拒绝降级更新", file=sys.stderr)
                return 1

    # 5. 安全解压 + 描述落盘（installed_files 清单）
    extract_plugin_pack(pack, name, meta_override=desc, clean_old=args.update)

    # 6. 依赖提示（不阻止安装）
    print(f"[提示] 插件依赖 dependencies={desc.get('dependencies', []) or []}")
    missing_pip = _check_pip_dependencies(desc.get('pip_dependencies', []))
    if missing_pip:
        print(f"[提示] 缺失 pip 依赖: {', '.join(missing_pip)}（插件启动时将跳过加载）")
        print(f"       安装：pip install {' '.join(missing_pip)}")

    action = '更新' if args.update else '安装'
    print(f"[OK] 插件 {name} v{version} {action}完成（文件已落盘，启动框架后自动加载）")
    return 0


# ---------------- frontend ----------------

def _load_frontend_config(base: str) -> list:
    cfg_file = global_var.FRONTEND_CONFIG_FILE
    if not os.path.isfile(cfg_file):
        return []
    try:
        with open(cfg_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_frontend_config(base: str, tools: list) -> None:
    cfg_file = global_var.FRONTEND_CONFIG_FILE
    os.makedirs(os.path.dirname(cfg_file), exist_ok=True)
    with open(cfg_file, 'w', encoding='utf-8') as f:
        json.dump(tools, f, ensure_ascii=False, indent=2)


def install_frontend(args, base: str) -> int:
    pack = os.path.abspath(args.pack)
    if not os.path.isfile(pack):
        print(f"错误：工具包不存在: {pack}", file=sys.stderr)
        return 1
    if not pack.endswith('.zip'):
        print("错误：工具包必须是 .zip 格式", file=sys.stderr)
        return 1

    # 1. 完整性校验
    vres = verify_package(pack, 'frontend')
    if not vres['ok']:
        print(f"错误：完整性校验失败: {vres['message']}", file=sys.stderr)
        return 1
    if vres.get('warn_only'):
        print(f"[警告] {vres['message']}")

    # 2. 读取并校验 config.json
    with zipfile.ZipFile(pack, 'r') as zf:
        names = [n.replace('\\', '/') for n in zf.namelist()]
        if 'config.json' not in names:
            print("错误：工具包缺少 config.json 配置文件", file=sys.stderr)
            return 1
        try:
            config = json.loads(zf.read('config.json').decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            print("错误：config.json 格式错误", file=sys.stderr)
            return 1
        if not isinstance(config, dict):
            print("错误：config.json 内容必须为 JSON 对象", file=sys.stderr)
            return 1
        for field in ('name', 'version', 'category'):
            if field not in config:
                print(f"错误：config.json 缺少必填字段: {field}", file=sys.stderr)
                return 1

        tool_name = config['name']
        html_file = f"{tool_name}.html"
        if html_file not in names:
            print(f"错误：工具包缺少入口文件: {html_file}", file=sys.stderr)
            return 1

        # 3. 框架版本校验
        if 'require_framework_version' in config:
            ok, msg = check_framework_version(config['require_framework_version'])
            if not ok:
                print(f"错误：{msg}", file=sys.stderr)
                return 1

        # 4. 静态扫描门禁
        _scan_gate_cli(pack, 'frontend', tool_name, args.no_scan)

        # 5. 同名与版本检查
        tools = _load_frontend_config(base)
        existing = next((t for t in tools if t['name'] == tool_name), None)
        if existing and not args.update:
            print(f"错误：前端工具 {tool_name} 已存在，更新请加 --update", file=sys.stderr)
            return 1
        if existing and compare_versions(str(config['version']), str(existing.get('version', '0'))) < 0:
            print(f"错误：包版本 {config['version']} 低于已装版本 {existing.get('version')}，拒绝降级更新",
                  file=sys.stderr)
            return 1

        # 6. 安全解压（更新时清理旧静态资源）
        html_path, static_files = safe_extract_frontend(
            zf, tool_name, global_var.FRONTEND_TEMPLATE_DIR, clean_static=args.update)

        # 7. 注册清单更新（与前端上传字段一致）
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        entry = {
            'name': tool_name,
            'title': config.get('title', tool_name),
            'permission': config.get('permission', 'public'),
            'author': config.get('author', '佚名'),
            'description': config.get('description', '暂无描述'),
            'version': str(config['version']),
            'category': config['category'],
            'require_framework_version': config.get('require_framework_version', ''),
            'enabled': True,
            'type': 'frontend',
            'install_time': existing.get('install_time', now) if existing else now,
            'source': os.path.basename(pack),
            'history': (existing.get('history', []) if existing else []) + [
                {'version': str(config['version']), 'time': now, 'source': os.path.basename(pack)}],
        }
        if existing:
            tools[tools.index(existing)] = entry
        else:
            tools.append(entry)
        _save_frontend_config(base, tools)

    action = '更新' if args.update else '安装'
    print(f"[OK] 前端工具 {tool_name} v{config['version']} {action}完成（入口 {html_file}，"
          f"静态文件 {len(static_files)} 个，启动框架后生效）")
    return 0


# ---------------- list ----------------

def cmd_list(base: str) -> int:
    print(f"框架根: {base}")
    plugins = sorted(f[:-3] for f in os.listdir(os.path.join(base, 'plugins'))
                     if f.endswith('.py') and f != 'base_plugin.py')
    print(f"\n已安装后端插件（{len(plugins)} 个）:")
    for p in plugins:
        meta_path = os.path.join(base, 'plugins', f'{p}.json')
        ver = ''
        if os.path.isfile(meta_path):
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    ver = str(json.load(f).get('version', ''))
            except Exception:
                pass
        print(f"  - {p}{' v' + ver if ver else ''}")

    tools = _load_frontend_config(base)
    print(f"\n已注册前端工具（{len(tools)} 个）:")
    for t in tools:
        print(f"  - {t.get('name')} v{t.get('version', '?')} [{t.get('permission', 'public')}] "
              f"{t.get('title', '')}")
    return 0


def main():
    ap = argparse.ArgumentParser(description='FlaskToolkit 插件手动安装 CLI（不跑框架时离线安装/查看）')
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--base', default=None, help='FlaskToolkit 框架根（缺省取本脚本上级目录）')
    sub = ap.add_subparsers(dest='action', required=True, help='backend=后端插件 / frontend=前端工具 / list=查看')

    p_backend = sub.add_parser('backend', parents=[common], help='安装/更新后端插件包（.zip）')
    p_backend.add_argument('pack', help='插件包路径（.zip）')
    p_backend.add_argument('--update', action='store_true', help='更新模式（按旧 installed_files 清理后重装）')
    p_backend.add_argument('--no-scan', action='store_true', help='跳过静态扫描门禁')

    p_frontend = sub.add_parser('frontend', parents=[common], help='安装/更新前端工具包（.zip）')
    p_frontend.add_argument('pack', help='工具包路径（.zip）')
    p_frontend.add_argument('--update', action='store_true', help='更新模式（清理旧静态资源后重装）')
    p_frontend.add_argument('--no-scan', action='store_true', help='跳过静态扫描门禁')

    sub.add_parser('list', parents=[common], help='列出已安装插件与前端工具')

    args = ap.parse_args()
    try:
        base = resolve_base(args.base)
        if args.action == 'backend':
            code = install_backend(args, base)
        elif args.action == 'frontend':
            code = install_frontend(args, base)
        else:
            code = cmd_list(base)
    except ValueError as e:
        print(f"错误：{e}", file=sys.stderr)
        code = 1
    except Exception as e:  # noqa: BLE001
        print(f"错误：{e}", file=sys.stderr)
        code = 1
    sys.exit(code)


if __name__ == '__main__':
    main()
