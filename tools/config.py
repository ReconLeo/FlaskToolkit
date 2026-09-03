# -*- coding: utf-8 -*-
"""FlaskToolkit 配置管理 CLI

让用户以命令行方式查看/修改框架的可配置项（路径、选项、运行参数），持久化到 data/user_config.json。
优先级：环境变量（HOST/PORT/DEBUG）> 用户配置文件 > 默认值。

用法：
  python tools/config.py show                    # 显示所有可配置项（默认值/当前生效值/来源）
  python tools/config.py set <key> <value>       # 设置配置项（自动校验类型并写入）
  python tools/config.py unset <key>             # 移除某项配置（恢复默认）
  python tools/config.py reset                   # 清空全部用户配置
  python tools/config.py check                   # 校验当前用户配置的合法性
  python tools/config.py env                     # 生成 .env.example 环境变量示例
  python tools/config.py profile                 # 查看配置预设（日常/加固/局域网开放）
  python tools/config.py profile <name>          # 应用一套预设（可再 set 单项覆盖）

示例：
  python tools/config.py set PACKAGE_MAX_UPLOAD_SIZE_MB 20
  python tools/config.py set PACKAGE_INTEGRITY_MODE strict
  python tools/config.py set LOG_DIR D:/logs/ftk
  python tools/config.py set HOST 0.0.0.0
  python tools/config.py set PORT 8080
  python tools/config.py set DEBUG true
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import global_var
from global_var import CONFIG_ITEMS, USER_CONFIG_FILE, coerce_config_value, load_user_config

ENV_MAP = {'HOST': 'FLASKTOOLKIT_HOST', 'PORT': 'FLASKTOOLKIT_PORT', 'DEBUG': 'FLASKTOOLKIT_DEBUG'}
KIND_LABEL = {'path': '路径', 'str': '文本', 'int': '整数', 'bool': '布尔', 'enum': '枚举'}


def _load_file() -> dict:
    if os.path.exists(USER_CONFIG_FILE):
        try:
            with open(USER_CONFIG_FILE, encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def _save_file(data: dict):
    os.makedirs(os.path.dirname(USER_CONFIG_FILE), exist_ok=True)
    with open(USER_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    load_user_config()


def _value_source(key: str) -> str:
    """判断当前生效值的来源：环境变量 > 用户配置 > 默认值"""
    if key in ENV_MAP:
        env = os.environ.get(ENV_MAP[key], '').strip()
        if env:
            return '环境变量'
    if key in _load_file():
        return '用户配置'
    return '默认值'


def _display_value(key: str, item: dict) -> str:
    """返回当前生效值（考虑环境变量/用户配置/默认值）"""
    if key in ENV_MAP:
        env = os.environ.get(ENV_MAP[key], '').strip()
        if env:
            return env
    data = _load_file()
    if key in data:
        return str(data[key])
    if key == 'PACKAGE_MAX_UPLOAD_SIZE_MB':
        return str(global_var.PACKAGE_MAX_UPLOAD_SIZE // (1024 * 1024))
    return str(getattr(global_var, key, item['default']))


def cmd_show(args):
    print(f"{'配置项':<28}{'当前值':<16}{'来源':<8}说明")
    print('-' * 100)
    for key, item in CONFIG_ITEMS.items():
        val = _display_value(key, item)
        src = _value_source(key)
        print(f"{key:<28}{val:<16}{src:<8}{item['desc']}")
    print(f"\n配置文件: {USER_CONFIG_FILE}")


def cmd_set(args):
    key = args.key
    if key not in CONFIG_ITEMS:
        print(f"错误：未知配置项 {key}。可用项: {', '.join(CONFIG_ITEMS.keys())}", file=sys.stderr)
        sys.exit(1)
    item = CONFIG_ITEMS[key]
    converted = coerce_config_value(args.value, item)
    if converted is None:
        hint = f"（可选值: {', '.join(item['choices'])}）" if item['kind'] == 'enum' else \
            (f"（需为整数）" if item['kind'] == 'int' else '')
        print(f"错误：{args.value!r} 不是合法的 {KIND_LABEL[item['kind']]} 值 {hint}", file=sys.stderr)
        sys.exit(1)
    data = _load_file()
    data[key] = converted
    _save_file(data)
    # 额外提示
    extra = ''
    if key == 'PACKAGE_MAX_UPLOAD_SIZE_MB':
        extra = f"（PACKAGE_MAX_UPLOAD_SIZE = {converted * 1024 * 1024} 字节）"
    elif key in ENV_MAP:
        extra = f"（也可通过环境变量 {ENV_MAP[key]} 设置，优先级更高）"
    print(f"已设置 {key} = {converted} {extra}")


def cmd_unset(args):
    key = args.key
    if key not in CONFIG_ITEMS:
        print(f"错误：未知配置项 {key}", file=sys.stderr)
        sys.exit(1)
    data = _load_file()
    if key in data:
        del data[key]
        _save_file(data)
        print(f"已移除 {key}（恢复默认值）")
    else:
        print(f"{key} 当前未设置（使用默认值）")


def cmd_reset(args):
    data = _load_file()
    if not data:
        print("用户配置为空，无需重置")
        return
    _save_file({})
    print(f"已清空全部用户配置（{len(data)} 项）")


def cmd_check(args):
    data = _load_file()
    if not data:
        print("用户配置为空（全部使用默认值），校验通过")
        return
    problems = []
    for key, value in data.items():
        if key not in CONFIG_ITEMS:
            problems.append(f"未知配置项: {key}")
            continue
        if coerce_config_value(value, CONFIG_ITEMS[key]) is None:
            item = CONFIG_ITEMS[key]
            hint = f"（可选值: {', '.join(item['choices'])}）" if item['kind'] == 'enum' else \
                (f"（需为整数）" if item['kind'] == 'int' else '')
            problems.append(f"{key} = {value!r} 非法 {KIND_LABEL[item['kind']]} {hint}")
    if problems:
        print("配置存在问题：")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print(f"校验通过（{len(data)} 项配置均合法）")


def cmd_env(args):
    lines = [
        "# FlaskToolkit 运行环境变量示例（复制为 .env 并按需修改）",
        "# 优先级：环境变量 > data/user_config.json > 默认值",
        "",
        "# 服务绑定地址（默认 127.0.0.1；局域网访问设 0.0.0.0）",
        "FLASKTOOLKIT_HOST=127.0.0.1",
        "",
        "# 服务端口（留空或不可用时自动探测）",
        "FLASKTOOLKIT_PORT=",
        "",
        "# 调试模式（1/true/yes/on 开启，生产环境保持关闭）",
        "FLASKTOOLKIT_DEBUG=false",
        "",
        "# 也可用 tools/config.py 持久化配置：python tools/config.py show",
    ]
    print('\n'.join(lines))
    print(f"\n（提示：也可以直接设置：python tools/config.py set HOST 0.0.0.0 等）")


# ------------------------------ 配置预设（v4.3.1） ------------------------------
# 统一管理分散的"严格模式"开关：一键应用一套场景化基线，之后仍可用 set 单项覆盖。
# 注意：应用预设会覆盖这些键上的既有用户配置。
PROFILES = {
    'daily': {
        'desc': '日常使用（框架默认基线：安全增强开启、安装拦截宽松）',
        'values': {
            'SECURITY_HEADERS': True,
            'SESSION_COOKIE_SECURE': False,
            'LOGIN_LOCK_MODE': 'ip_username',
            'LOGIN_MAX_ATTEMPTS': 5,
            'LOGIN_LOCK_SECONDS': 900,
            'SESSION_IDLE_TIMEOUT': 1800,
            'PACKAGE_INTEGRITY_MODE': 'warn',
            'PLUGIN_STRICT_MODE': False,
            'PLUGIN_SCAN_MODE': 'report',
            'AUDIT_HOOK_MODE': 'observe',
            'MAX_UPLOAD_SIZE_MB': 100,
        },
    },
    'strict': {
        'desc': '运维加固（完整性强制、扫描高风险拒绝安装、依赖严格、会话收紧；需 HTTPS 部署）',
        'values': {
            'SECURITY_HEADERS': True,
            'SESSION_COOKIE_SECURE': True,
            'LOGIN_LOCK_MODE': 'ip_username',
            'LOGIN_MAX_ATTEMPTS': 3,
            'LOGIN_LOCK_SECONDS': 1800,
            'SESSION_IDLE_TIMEOUT': 900,
            'PACKAGE_INTEGRITY_MODE': 'strict',
            'PLUGIN_STRICT_MODE': True,
            'PLUGIN_SCAN_MODE': 'enforce',
            'AUDIT_HOOK_MODE': 'enforce',
            'MAX_UPLOAD_SIZE_MB': 100,
        },
    },
    'lan-open': {
        'desc': '可信局域网开放（免登录锁定、免安装扫描；仅在内网用户与插件来源完全可信时使用）',
        'values': {
            'SECURITY_HEADERS': True,
            'SESSION_COOKIE_SECURE': False,
            'LOGIN_LOCK_MODE': 'off',
            'PACKAGE_INTEGRITY_MODE': 'warn',
            'PLUGIN_STRICT_MODE': False,
            'PLUGIN_SCAN_MODE': 'off',
            'AUDIT_HOOK_MODE': 'off',
            'MAX_UPLOAD_SIZE_MB': 100,
        },
    },
}


def apply_profile(name: str, config_file: str = None) -> dict:
    """应用一套配置预设，返回 {key: (旧值, 新值)} 变更清单；未知预设抛 ValueError"""
    if name not in PROFILES:
        raise ValueError(f'未知预设: {name}（可选: {", ".join(PROFILES)}）')
    target = config_file or USER_CONFIG_FILE
    data = {}
    if os.path.exists(target):
        try:
            with open(target, encoding='utf-8') as f:
                data = json.load(f)
            data = data if isinstance(data, dict) else {}
        except Exception:
            data = {}
    changes = {}
    for key, value in PROFILES[name]['values'].items():
        coerced = coerce_config_value(value, CONFIG_ITEMS[key])
        changes[key] = (data.get(key, CONFIG_ITEMS[key]['default']), coerced)
        data[key] = coerced
    os.makedirs(os.path.dirname(target) or '.', exist_ok=True)
    with open(target, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    if target == USER_CONFIG_FILE:
        load_user_config()
    return changes


def cmd_profile(args):
    if not getattr(args, 'name', None):
        print('可用配置预设：')
        for name, prof in PROFILES.items():
            print(f'  {name:<10} {prof["desc"]}')
        print('\n应用: python tools/config.py profile <name>（会覆盖下列键的既有用户配置，之后可 set 单项微调）')
        return
    try:
        changes = apply_profile(args.name)
    except ValueError as e:
        print(f'错误: {e}', file=sys.stderr)
        sys.exit(2)
    print(f'已应用预设 [{args.name}]：{PROFILES[args.name]["desc"]}')
    for key, (old, new) in changes.items():
        mark = '' if old == new else f'（原 {old}）'
        print(f'  {key:<24} = {new} {mark}')
    print('（重启服务后生效；单项微调: python tools/config.py set <key> <value>）')


def main():
    ap = argparse.ArgumentParser(description='FlaskToolkit 配置管理 CLI')
    sub = ap.add_subparsers(dest='cmd', required=True)

    sub.add_parser('show', help='显示所有可配置项').set_defaults(func=cmd_show)

    s = sub.add_parser('set', help='设置配置项')
    s.add_argument('key', help='配置项名称')
    s.add_argument('value', help='配置值')
    s.set_defaults(func=cmd_set)

    u = sub.add_parser('unset', help='移除配置项（恢复默认）')
    u.add_argument('key')
    u.set_defaults(func=cmd_unset)

    sub.add_parser('reset', help='清空全部用户配置').set_defaults(func=cmd_reset)
    sub.add_parser('check', help='校验配置合法性').set_defaults(func=cmd_check)
    sub.add_parser('env', help='生成环境变量示例').set_defaults(func=cmd_env)

    p = sub.add_parser('profile', help='查看/应用配置预设')
    p.add_argument('name', nargs='?', help='预设名：daily / strict / lan-open（缺省为列出）')
    p.set_defaults(func=cmd_profile)

    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
