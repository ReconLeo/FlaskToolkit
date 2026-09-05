# -*- coding: utf-8 -*-
"""FlaskToolkit 深度重置命令行工具（服务停止时使用）

用途：
- 在服务运行时无法重置的内容（文件被占用/锁定、API 层面重置受沙箱/权限限制）可通过
  本工具在服务停止状态下直接操作文件系统完成重置。
- 复用 core/factory_reset 的范围语义；支持 --auto-backup 先备份再重置（呼应手动备份）。

用法：
  python tools/reset.py list                            # 列出可重置范围
  python tools/reset.py reset <scope> [scope...]        # 重置指定范围
  python tools/reset.py reset all                       # 全部重置
  python tools/reset.py reset all --auto-backup         # 先自动备份再全部重置

范围说明（与 Factory Reset 一致）：
  plugins        清除非内置插件（含文件/模板/静态/配置；内置 auth/user_manage 受保护）
  （locales/ 为框架内置 i18n 语言包，属框架数据，不在任何重置范围内；用户扩展语言包
    与用户配置同类，深度重置同样保留，与 Factory Reset 语义一致）
  frontend_tools 清空前端工具（注册清单 + 模板目录）
  stats_logs     重置统计数据（data/stats.json + 内存统计）与日志目录
  sessions       清空登录会话
  temp           清理 temp/、.plugin_cache、__pycache__
  builtin        重置内置插件配置（auth 恢复默认 admin/admin123）
  all            以上全部
"""
import argparse
import os
import socket
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import global_var
from core.factory_reset import factory_reset

SCOPE_HELP = {
    'plugins': '清除非内置插件（内置 auth/user_manage 受保护）',
    'frontend_tools': '清空前端工具（清单 + 模板目录）',
    'stats_logs': '重置统计数据与日志目录',
    'sessions': '清空登录会话',
    'temp': '清理临时文件/缓存/__pycache__',
    'builtin': '重置内置插件配置（auth 恢复默认 admin/admin123）',
    'all': '以上全部',
}


def is_service_running() -> bool:
    """检测服务监听地址是否有服务在运行（提示用，非强制）。

    适配用户配置 HOST/PORT（tools/config.py 可设，环境变量 FLASKTOOLKIT_HOST/PORT 优先）；
    PORT 留空时框架自动探测可用端口，此处回退默认 5000 提示。
    """
    host, port = '127.0.0.1', 5000
    try:
        cfg = global_var.get_user_config()
        host = cfg.get('HOST') or host
        port = int(cfg.get('PORT') or port)
    except Exception:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


def cmd_list(args):
    print("可重置范围（与 Factory Reset 一致）：")
    print(f"{'scope':<16}说明")
    print('-' * 60)
    for k, v in SCOPE_HELP.items():
        print(f"{k:<16}{v}")


def cmd_reset(args):
    if is_service_running():
        print("⚠ 检测到服务可能正在运行（127.0.0.1:5000）。建议先停止服务再执行深度重置，"
              "否则部分文件可能被占用导致删除失败。", flush=True)
    scopes = args.scopes
    if 'all' in scopes:
        scopes = ['all']
    if args.auto_backup:
        print("--auto-backup: 先执行备份...")
        from tools import backup
        dest, saved, skipped = backup.create_backup()
        print(f"  备份完成: {dest}（{len(saved)} 项）")
    print(f"执行重置: {scopes}")
    res = factory_reset(scopes)
    cleaned = res.get('cleaned', [])
    failed = res.get('failed', [])
    print(f"清理 {len(cleaned)} 项: {', '.join(cleaned)}" if cleaned else "清理 0 项")
    if failed:
        print(f"失败 {len(failed)} 项:", file=sys.stderr)
        for item in failed:
            print(f"  - {item}", file=sys.stderr)
    if args.auto_backup:
        print("如需回滚，可执行: python tools/backup.py restore "
              f"{os.path.basename(dest)}")
    sys.exit(0 if not failed else 1)


def main():
    ap = argparse.ArgumentParser(description='FlaskToolkit 深度重置工具（建议服务停止时使用）')
    sub = ap.add_subparsers(dest='cmd', required=True)

    sub.add_parser('list', help='列出可重置范围').set_defaults(func=cmd_list)

    r = sub.add_parser('reset', help='深度重置指定范围')
    r.add_argument('scopes', nargs='+', help='范围（多个用空格分隔，或 all）')
    r.add_argument('--auto-backup', action='store_true', help='重置前自动备份关键数据')
    r.set_defaults(func=cmd_reset)

    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
