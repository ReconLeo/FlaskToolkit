# -*- coding: utf-8 -*-
"""FlaskToolkit 手动备份 / 恢复工具（呼应 Factory Reset 的手动备份）

用途：
- 在 Factory Reset（重置）前手动备份关键数据，支持重置后还原。
- 备份内容默认覆盖：插件配置（plugins/configs）、插件启用状态（plugins/status.json）、
  插件会话（plugins/data）、运行数据（data：统计/审计日志/用户配置）、前端工具清单
  （data/frontend_tools.json，v4.5.0 起随前端工具清单迁移至 data/）、日志（logs）。
- 建议在服务停止时执行（避免文件被占用）。

用法：
  python tools/backup.py create [名称]        # 创建备份（默认时间戳命名）
  python tools/backup.py list                  # 列出已有备份
  python tools/backup.py restore <名称|路径>   # 恢复备份到项目（覆盖式）
  python tools/backup.py info <名称|路径>      # 查看某备份内容清单
"""
import argparse
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import global_var

BACKUP_ROOT = os.path.join(global_var.BASE_DIR, 'backups')

# (源相对项目根, 备份内相对路径)
BACKUP_ITEMS = [
    ('plugins/configs', 'plugins/configs'),
    ('plugins/status.json', 'plugins/status.json'),
    ('plugins/data', 'plugins/data'),
    ('data', 'data'),
    ('data/frontend_tools.json', 'data/frontend_tools.json'),
    ('logs', 'logs'),
]


def _resolve(name_or_path: str) -> str:
    """接受备份名或路径，返回备份目录绝对路径"""
    if os.path.isabs(name_or_path):
        return name_or_path
    return os.path.join(BACKUP_ROOT, name_or_path)


def create_backup(name: str = '') -> tuple:
    """创建备份，返回 (备份目录, 已备份条目列表)。name 为空用时间戳。"""
    ts = name or time.strftime('%Y%m%d_%H%M%S')
    dest = os.path.join(BACKUP_ROOT, ts)
    if os.path.exists(dest):
        raise FileExistsError(f"备份已存在: {dest}")
    os.makedirs(dest, exist_ok=True)
    saved = []
    skipped = []
    for src, rel in BACKUP_ITEMS:
        full = os.path.join(global_var.BASE_DIR, src)
        if not os.path.exists(full):
            skipped.append(rel)
            continue
        dst = os.path.join(dest, rel)
        try:
            if os.path.isdir(full):
                shutil.copytree(full, dst)
            else:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(full, dst)
            saved.append(rel)
        except Exception as e:
            skipped.append(f"{rel}（{e}）")
    manifest = {'created': time.strftime('%Y-%m-%d %H:%M:%S'), 'items': saved}
    with open(os.path.join(dest, 'backup.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return dest, saved, skipped


def list_backups() -> list:
    """列出所有备份（按名称倒序）"""
    if not os.path.isdir(BACKUP_ROOT):
        return []
    out = []
    for name in sorted(os.listdir(BACKUP_ROOT), reverse=True):
        d = os.path.join(BACKUP_ROOT, name)
        if os.path.isdir(d) and os.path.exists(os.path.join(d, 'backup.json')):
            try:
                m = json.load(open(os.path.join(d, 'backup.json'), encoding='utf-8'))
            except Exception:
                m = {}
            out.append({'name': name, 'created': m.get('created', ''), 'items': m.get('items', [])})
    return out


def info_backup(name_or_path: str) -> dict:
    d = _resolve(name_or_path)
    if not os.path.exists(d):
        raise FileNotFoundError(f"备份不存在: {d}")
    try:
        m = json.load(open(os.path.join(d, 'backup.json'), encoding='utf-8'))
    except Exception:
        m = {}
    return {'path': d, 'created': m.get('created', ''), 'items': m.get('items', [])}


def restore_backup(name_or_path: str) -> list:
    """把备份内容覆盖式恢复回项目（存在同路径则先清空目录再拷入）"""
    d = _resolve(name_or_path)
    if not os.path.isdir(d):
        raise FileNotFoundError(f"备份不存在: {d}")
    restored = []
    for rel in BACKUP_ITEMS:
        src = os.path.join(d, rel[1])
        if not os.path.exists(src):
            continue
        dst = os.path.join(global_var.BASE_DIR, rel[0])
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.isdir(src):
            # 目标目录已存在：先移除旧内容再整体恢复（确保干净还原）
            if os.path.isdir(dst):
                try:
                    shutil.rmtree(dst, ignore_errors=True)
                except Exception as e:
                    print(f"警告: 清理旧目录失败 {dst}（{e}），将覆盖式合并")
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        restored.append(rel[0])
    return restored


def main():
    ap = argparse.ArgumentParser(description='FlaskToolkit 手动备份/恢复工具')
    sub = ap.add_subparsers(dest='cmd', required=True)

    c = sub.add_parser('create', help='创建备份')
    c.add_argument('name', nargs='?', default='', help='备份名称（默认时间戳）')
    c.set_defaults(func=lambda a: _cmd_create(a))

    sub.add_parser('list', help='列出备份').set_defaults(func=lambda a: _cmd_list())

    i = sub.add_parser('info', help='查看备份内容')
    i.add_argument('name_or_path')
    i.set_defaults(func=lambda a: _cmd_info(a))

    r = sub.add_parser('restore', help='恢复备份')
    r.add_argument('name_or_path')
    r.set_defaults(func=lambda a: _cmd_restore(a))

    args = ap.parse_args()
    args.func(args)


def _cmd_create(args):
    dest, saved, skipped = create_backup(args.name)
    print(f"备份已创建: {dest}")
    print(f"  已备份 {len(saved)} 项: {', '.join(saved)}")
    if skipped:
        print(f"  跳过 {len(skipped)} 项: {', '.join(skipped)}")
    print(f"提示: 恢复使用 python tools/backup.py restore {os.path.basename(dest)}")


def _cmd_list():
    backs = list_backups()
    if not backs:
        print("暂无备份")
        return
    print(f"{'名称':<22}{'创建时间':<20}内容")
    print('-' * 80)
    for b in backs:
        print(f"{b['name']:<22}{b['created']:<20}{', '.join(b['items'][:6])}")


def _cmd_info(args):
    try:
        info = info_backup(args.name_or_path)
    except FileNotFoundError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"备份路径: {info['path']}")
    print(f"创建时间: {info['created']}")
    print(f"内容条目: {', '.join(info['items'])}")


def _cmd_restore(args):
    try:
        restored = restore_backup(args.name_or_path)
    except FileNotFoundError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"已恢复 {len(restored)} 项: {', '.join(restored)}")
    print("提示: 建议在服务停止状态恢复，恢复后重启服务生效。")


if __name__ == '__main__':
    main()
