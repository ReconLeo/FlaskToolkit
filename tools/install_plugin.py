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
  python tools/install_plugin.py uninstall backend demo_plugin [--purge-data]
  python tools/install_plugin.py uninstall frontend my_tool [--purge-data]
  python tools/install_plugin.py list
  # 指定框架根（默认脚本上级目录，即本仓库根）：
  python tools/install_plugin.py backend demo_plugin.zip --base /path/to/FlaskToolkit

说明：
- 安装/更新后插件在下次启动框架时自动加载（本工具不启动服务）。
- 同名插件存在时需 --update（按旧 installed_files 清单清理旧文件后解压新包）；
  --update 仅当包内 plugin.json 版本不低于已装版本时执行。
- 卸载（uninstall，v4.10 M6-Extra）：按 installed_files 清单删除插件引入文件 +
  配置；--purge-data 一并清理插件全部数据（plugins/data/ + plugins/temp/ + capabilities
  filesystem:write 声明目录）。离线卸载不执行插件 on_uninstall 钩子；内置插件受保护。
- 静态扫描默认按 PLUGIN_SCAN_MODE（off/report/enforce）执行；--no-scan 完全跳过。
  v4.23.5：--scan-mode 可显式覆盖扫描模式，并始终打印「生效模式 + 来源」——`--base` 指向
  隔离运行时时，扫描模式**不读**目标环境配置（仍是工具所在框架的 global_var/user_config），
  此前容易误判"enforce 生效了/没生效"。判定统一走 core.plugin_scanner.evaluate_gate。

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
from core.plugin_pack import (cleanup_plugin_data, cleanup_plugin_resources,  # noqa: E402
                              compare_versions, check_framework_version,
                              extract_plugin_pack, parse_plugin_pack,
                              plugin_main_file, plugin_meta_file)
from core.package_sign import verify_package  # noqa: E402
from routes.frontend import cleanup_frontend_resources, safe_extract_frontend  # noqa: E402
from core.frontend_tools import load_frontend_tools  # noqa: E402
from core.plugin_scanner import (  # noqa: E402
    scan_plugin_zip, scan_frontend_zip, evaluate_gate, format_finding,
)
from core.capabilities import read_pack_capabilities, cross_validate  # noqa: E402
from core.plugin_deps import check_pip_dependencies, dep_name  # noqa: E402

DEFAULT_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 扫描模式来源（v4.23.5）：--scan-mode 显式覆盖 / 工具所在框架的配置；供 CLI 明确打印
_SCAN_MODE_SOURCE = 'default'


def _scan_mode_source() -> str:
    """当前生效扫描模式的来源说明（消除「--base 改了 enforce 却不生效」的误判）。"""
    if _SCAN_MODE_SOURCE == 'cli':
        return '--scan-mode 显式指定'
    if _SCAN_MODE_SOURCE == 'no-scan':
        return '--no-scan 跳过扫描'
    return (f'{os.path.join(DEFAULT_BASE, "global_var.py")} 的 PLUGIN_SCAN_MODE '
            f'（或 data/user_config.json 覆盖值）；--base 只影响目标路径，不影响扫描模式')


def _apply_scan_mode(args):
    """应用 --scan-mode 显式覆盖（off/report/enforce）；记录来源供打印。"""
    global _SCAN_MODE_SOURCE
    mode = getattr(args, 'scan_mode', None)
    if mode:
        global_var.PLUGIN_SCAN_MODE = mode
        _SCAN_MODE_SOURCE = 'cli'
    if getattr(args, 'no_scan', False):
        global_var.PLUGIN_SCAN_MODE = 'off'
        _SCAN_MODE_SOURCE = 'no-scan'


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


def _scan_gate_cli(zip_path: str, kind: str, name: str, no_scan: bool, base=None):
    """静态扫描门禁（与框架行为一致：off 跳过 / report 打印摘要 / enforce 拒绝）。
    v4.23.5 起判定统一走 core.plugin_scanner.evaluate_gate（与 Web/服务层同一份逻辑）：
    - 不可约束 high（eval/exec/pickle/混淆/动态导入/socket.bind/subprocess…）：capabilities 不能背书，
      唯一通路是该行 `# scan:ignore`（Community：enforce 是「知情声明」防线，不是沙箱）；
    - 可约束 high（shutil.rmtree 常量路径）：按 filesystem:write 归因豁免，未归因仍拒；
    - 子进程另加归因闸门：即使该行已 `# scan:ignore`，仍须声明匹配的 process:exec[:<bin>]。"""
    print(f"[扫描] 模式={global_var.PLUGIN_SCAN_MODE}（来源：{_scan_mode_source()}）")
    if no_scan or global_var.PLUGIN_SCAN_MODE == 'off':
        return
    report = scan_plugin_zip(zip_path) if kind == 'backend' else scan_frontend_zip(zip_path)
    cap_res = None
    if kind == 'backend':
        try:
            caps = read_pack_capabilities(zip_path)
            cap_res = cross_validate(name, report, caps, base_dir=base)
            report['capabilities'] = cap_res
        except Exception:
            cap_res = None
    gate = evaluate_gate(report, cap_res)
    if report['summary']['high'] > 0:
        print(f"[扫描] {name} 发现 {report['summary']['high']} 项高风险行为:")
        for item in report['findings']:
            if item.get('severity') == 'high':
                print(f"       - {format_finding(item, cap_res)}")
    elif not gate['blocked']:
        print(f"[扫描] {name} 静态扫描通过（{report['summary'].get('info', 0)} 项提示）")
    if gate['blocked']:
        if global_var.PLUGIN_SCAN_MODE != 'enforce':
            print("[扫描] 以上高风险在 report 模式下放行（enforce 模式将拒绝安装）")
            return
        for reason in gate['reasons']:
            print(f"[拒绝原因] {reason}", file=sys.stderr)
        raise ValueError(
            "静态扫描存在不可放行的高风险行为：" + '；'.join(gate['reasons'])
            + f"，PLUGIN_SCAN_MODE=enforce 已拒绝安装（--no-scan 会整体跳过扫描门禁，慎用）")


def _check_pip_dependencies(pip_deps):
    """检测 pip_dependencies 未就绪项（支持 name>=x 与版本约束），返回 [(spec, 原因)]。

    复用 core.plugin_deps.check_pip_dependencies，与加载阶段/Web 安装拦截语义一致
    （此前自实现的版本直接拿原始 spec 去 importlib.metadata.distribution，带版本约束会误报缺失）。
    缺失不阻止 CLI 安装，但**必须以警告级别明确提示**：否则用户会得到"插件装上却找不到"的困惑。
    """
    try:
        return check_pip_dependencies(pip_deps)
    except Exception:
        return []


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
    _scan_gate_cli(pack, 'backend', name, args.no_scan, base)

    # 4. 同名与版本检查
    plugin_file = plugin_main_file(base, name)
    existing_meta = None
    meta_path = plugin_meta_file(base, name)
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

    # 6. 依赖提示（不阻止安装，但缺失 pip 依赖必须以警告级别醒目提示）
    print(f"[提示] 插件依赖 dependencies={desc.get('dependencies', []) or []}")
    missing_pip = _check_pip_dependencies(desc.get('pip_dependencies'))
    if missing_pip:
        print(f"[警告] 缺失 pip 依赖 {len(missing_pip)} 项 —— 插件会被跳过加载（后台显示「未加载」）:",
              file=sys.stderr)
        for spec, why in missing_pip:
            print(f"       - {spec}：{why}", file=sys.stderr)
        _pkg_names = ' '.join(dep_name(spec) for spec, _ in missing_pip)
        print(f"       安装：{sys.executable} -m pip install {_pkg_names}", file=sys.stderr)

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
        _scan_gate_cli(pack, 'frontend', tool_name, args.no_scan, base)

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
    plugin_dir = os.path.join(base, 'plugins')
    _names = []
    for f in sorted(os.listdir(plugin_dir)):
        full = os.path.join(plugin_dir, f)
        if f.endswith('.py') and f not in ('base_plugin.py', '__init__.py'):
            _names.append(f[:-3])  # 扁平主文件
        elif os.path.isdir(full) and os.path.isfile(os.path.join(full, f'{f}.py')):
            _names.append(f)  # 目录化主文件
    plugins = sorted(set(_names))
    print(f"\n已安装后端插件（{len(plugins)} 个）:")
    for p in plugins:
        meta_path = plugin_meta_file(base, p)
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


# ---------------- uninstall ----------------

def uninstall_backend(args, base: str) -> int:
    name = args.name
    if name in global_var.BUILTIN_PLUGINS:
        print(f"错误：内置插件 {name} 受保护，不允许卸载", file=sys.stderr)
        return 1
    plugin_file = plugin_main_file(base, name)
    if not os.path.isfile(plugin_file):
        print(f"错误：插件 {name} 不存在（plugins/{name}.py）", file=sys.stderr)
        return 1

    removed = []
    # 1. 数据空间（--purge-data 时先清理：此时描述文件仍在，可解析 capabilities
    #    filesystem:write 声明目录；随后文件删除会移除描述文件）
    if args.purge_data:
        removed += cleanup_plugin_data(name, include_data=True, base_dir=base)
        data_note = ''
    else:
        data_note = '（--purge-data 可一并清理 plugins/data/<name>/、临时目录与 filesystem:write 声明目录）'
    # 2. 主文件 + installed_files 清单引入的全部文件（含描述文件/模板/静态）
    os.remove(plugin_file)
    removed.append(plugin_file)
    removed += cleanup_plugin_resources(name)
    # 3. 插件配置
    cfg = os.path.join(global_var.PLUGIN_CONFIGS_DIR, f'{name}.json')
    if os.path.isfile(cfg):
        os.remove(cfg)
        removed.append(cfg)

    print(f"[OK] 插件 {name} 已卸载（清理 {len(removed)} 项；离线卸载不执行 on_uninstall 钩子，启动框架后自动从列表移除）")
    print(f"      {data_note}" if data_note else "      数据空间已随卸载清理")
    # v4.15.4：离线卸载一并清理该插件统计残留（call_stats / daily_stats）
    try:
        from core.stats import load_stats, purge_plugin_stats
        load_stats()
        if purge_plugin_stats(name):
            print(f"      [OK] 已清理插件 {name} 的统计残留")
    except Exception as _e:
        print(f"      [warn] 统计残留清理失败: {_e}", file=sys.stderr)
    return 0


def uninstall_frontend(args, base: str) -> int:
    name = args.name
    tools = _load_frontend_config(base)
    existing = next((t for t in tools if t['name'] == name), None)
    if not existing:
        print(f"错误：前端工具 {name} 不存在（未注册）", file=sys.stderr)
        return 1
    removed = cleanup_frontend_resources(name)
    tools = [t for t in tools if t['name'] != name]
    _save_frontend_config(base, tools)
    print(f"[OK] 前端工具 {name} 已卸载（清理 {len(removed)} 项；前端工具无数据目录）")
    # v4.15.4：离线卸载一并清理该前端工具统计残留（frontend_access_stats / daily_stats）
    try:
        from core.stats import load_stats, purge_frontend_tool_stats
        load_stats()
        if purge_frontend_tool_stats(name):
            print(f"      [OK] 已清理前端工具 {name} 的统计残留")
    except Exception as _e:
        print(f"      [warn] 统计残留清理失败: {_e}", file=sys.stderr)
    return 0


def main():
    ap = argparse.ArgumentParser(description='FlaskToolkit 插件手动安装/卸载 CLI（不跑框架时离线操作）')
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--base', default=None, help='FlaskToolkit 框架根（缺省取本脚本上级目录）')
    sub = ap.add_subparsers(dest='action', required=True, help='backend=后端插件 / frontend=前端工具 / list=查看')

    p_backend = sub.add_parser('backend', parents=[common], help='安装/更新后端插件包（.zip）')
    p_backend.add_argument('pack', help='插件包路径（.zip）')
    p_backend.add_argument('--update', action='store_true', help='更新模式（按旧 installed_files 清理后重装）')
    p_backend.add_argument('--no-scan', action='store_true', help='跳过静态扫描门禁')
    p_backend.add_argument('--scan-mode', choices=['off', 'report', 'enforce'], default=None,
                           help='显式指定静态扫描模式（缺省取工具所在框架配置；--base 不影响模式）')

    p_frontend = sub.add_parser('frontend', parents=[common], help='安装/更新前端工具包（.zip）')
    p_frontend.add_argument('pack', help='工具包路径（.zip）')
    p_frontend.add_argument('--update', action='store_true', help='更新模式（清理旧静态资源后重装）')
    p_frontend.add_argument('--no-scan', action='store_true', help='跳过静态扫描门禁')
    p_frontend.add_argument('--scan-mode', choices=['off', 'report', 'enforce'], default=None,
                            help='显式指定静态扫描模式（缺省取工具所在框架配置；--base 不影响模式）')

    p_uninstall = sub.add_parser('uninstall', parents=[common], help='卸载插件/前端工具（离线）')
    un_sub = p_uninstall.add_subparsers(dest='un_kind', required=True, help='backend=后端插件 / frontend=前端工具')
    un_b = un_sub.add_parser('backend', parents=[common], help='卸载后端插件')
    un_b.add_argument('name', help='插件名')
    un_b.add_argument('--purge-data', action='store_true',
                      help='一并清理插件全部数据（plugins/data/ + 临时 + filesystem:write 声明目录）')
    un_f = un_sub.add_parser('frontend', parents=[common], help='卸载前端工具')
    un_f.add_argument('name', help='工具名')
    un_f.add_argument('--purge-data', action='store_true', help='前端工具无数据目录，无效果（保留参数一致）')

    sub.add_parser('list', parents=[common], help='列出已安装插件与前端工具')

    args = ap.parse_args()
    try:
        base = resolve_base(args.base)
        _apply_scan_mode(args)
        if args.action == 'backend':
            code = install_backend(args, base)
        elif args.action == 'frontend':
            code = install_frontend(args, base)
        elif args.action == 'uninstall':
            code = (uninstall_backend(args, base) if args.un_kind == 'backend'
                    else uninstall_frontend(args, base))
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
