# -*- coding: utf-8 -*-
"""旧扁平插件布局 → 目录化自包含布局 迁移工具（v4.21）

背景：v4.21 起插件从"plugins/ 根扁平安装"改为"每个插件一个自包含目录 plugins/<name>/"，
辅助模块/描述文件/locales 全部进入插件私有命名空间，消除多插件同名辅助模块/模板冲突。
本工具把已安装的旧扁平第三方插件迁移到 plugins/<name>/，使 loader（不再向前兼容扁平辅助模块）
能继续正常发现与加载。

用法：
  python tools/migrate_plugin_layout.py --base /path/to/FlaskToolkit [--dry-run]
  python tools/migrate_plugin_layout.py --dry-run --base /path/to/FlaskToolkit   # 仅预览不落盘
  python tools/migrate_plugin_layout.py --plugin corp_tools --base ...           # 仅迁移指定插件

迁移内容（每插件）：
- 主文件  plugins/<name>.py                → plugins/<name>/<name>.py
- 描述    plugins/<name>.json              → plugins/<name>/<name>.json
- 辅助模块（描述 installed_files 清单，或主文件源码 `from plugins import X` / `import plugins.X` 扫描）
           plugins/X.py                    → plugins/<name>/X.py
- locales  plugins/<name>/locales/（已目录化，不迁移；扁平期通常无）
- 生成    plugins/<name>/__init__.py（包标记，使 plugins.<name> 可作包导入）
- 更新描述 installed_files 中对应相对路径为 plugins/<name>/<basename>

内置插件（auth/user_manage）跳过：auth 保留扁平（无辅助模块）；user_manage 已在仓库目录化。
"""
import argparse
import json
import os
import re
import shutil
import sys

# 允许直接运行（python tools/migrate_plugin_layout.py ...）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import global_var

# 内置插件：不迁移（auth 保留扁平；user_manage 已目录化）
SKIP = set(global_var.BUILTIN_PLUGINS)
SKIP_FILE = {'__init__.py', 'base_plugin.py'}
# 描述文件 installed_files 中属"插件私有命名空间"的相对路径前缀（plugins/ 根下）
_IMPORT_RE = re.compile(
    r'^\s*from\s+plugins\s+import\s+([A-Za-z_][A-Za-z0-9_]*)'
    r'|^\s*import\s+plugins\.([A-Za-z_][A-Za-z0-9_]*)\s*$')


def _find_plugins(base: str) -> list:
    """列出待迁移的扁平插件名（plugins/*.py 主文件，排除内置/框架文件/辅助模块）。

    仅迁移"有独立描述文件 <name>.json"的才是主插件；辅助模块（无描述）不单独迁移，
    随其所属插件由 installed_files 清单 / import 扫描一并迁入插件私有目录。
    """
    plugin_dir = os.path.join(base, 'plugins')
    if not os.path.isdir(plugin_dir):
        return []
    out = []
    for fn in sorted(os.listdir(plugin_dir)):
        if fn.endswith('.py') and fn not in SKIP_FILE and fn[:-3] not in SKIP:
            name = fn[:-3]
            if os.path.isfile(os.path.join(plugin_dir, f'{name}.json')):
                out.append(name)
    return out


def _scan_imported_helpers(main_py: str) -> list:
    """从主文件源码扫描 `from plugins import X` / `import plugins.X` 的辅助模块名。"""
    try:
        with open(main_py, 'r', encoding='utf-8') as f:
            src = f.read()
    except Exception:
        return []
    names = set()
    for m in _IMPORT_RE.finditer(src):
        names.add(m.group(1) or m.group(2))
    return sorted(names)


def _resolve_helpers(base: str, name: str, main_py: str) -> list:
    """确定要一并迁移的辅助模块 .py（相对 plugins/ 根）。installed_files 优先，源码 import 兜底。"""
    helpers = set()
    meta_file = os.path.join(base, 'plugins', f'{name}.json')
    if os.path.isfile(meta_file):
        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            for rel in meta.get('installed_files', []) or []:
                if (isinstance(rel, str) and rel.startswith('plugins/') and rel.endswith('.py')
                        and '/' not in rel[len('plugins/'):]  # plugins/<helper>.py（根辅助模块）
                        and os.path.basename(rel) != f'{name}.py'):
                    helpers.add(os.path.basename(rel))
        except Exception:
            pass
    for h in _scan_imported_helpers(main_py):
        if h != name and os.path.isfile(os.path.join(base, 'plugins', f'{h}.py')):
            helpers.add(f'{h}.py')
    return sorted(helpers)


def migrate_plugin(base: str, name: str, dry_run: bool) -> int:
    """迁移单个扁平插件到目录化布局。返回 0=成功/无需迁移，1=失败。"""
    plugin_dir = os.path.join(base, 'plugins')
    old_main = os.path.join(plugin_dir, f'{name}.py')
    old_meta = os.path.join(plugin_dir, f'{name}.json')
    if not os.path.isfile(old_main):
        print(f"  跳过：主文件不存在 plugins/{name}.py")
        return 0
    if os.path.isdir(os.path.join(plugin_dir, name)):
        print(f"  跳过：已是目录化布局 plugins/{name}/")
        return 0

    new_dir = os.path.join(plugin_dir, name)
    helpers = _resolve_helpers(base, name, old_main)

    print(f"迁移插件 {name}:")
    print(f"  主文件   plugins/{name}.py -> plugins/{name}/{name}.py")
    for h in helpers:
        print(f"  辅助模块 plugins/{h} -> plugins/{name}/{h}")
    if os.path.isfile(old_meta):
        print(f"  描述文件 plugins/{name}.json -> plugins/{name}/{name}.json")

    if dry_run:
        return 0

    try:
        os.makedirs(new_dir, exist_ok=True)
        # 主文件 + 描述
        shutil.move(old_main, os.path.join(new_dir, f'{name}.py'))
        if os.path.isfile(old_meta):
            shutil.move(old_meta, os.path.join(new_dir, f'{name}.json'))
        # 辅助模块
        for h in helpers:
            src = os.path.join(plugin_dir, h)
            if os.path.isfile(src):
                shutil.move(src, os.path.join(new_dir, h))
        # 已目录化 locales/（若有则保留，天然兼容）
        # 生成 __init__.py（空包标记）
        init = os.path.join(new_dir, '__init__.py')
        if not os.path.isfile(init):
            with open(init, 'w', encoding='utf-8') as f:
                f.write('# -*- coding: utf-8 -*-\n')
        # 更新描述 installed_files 相对路径（plugins/<x>.py -> plugins/<name>/<x>.py）
        meta_path = os.path.join(new_dir, f'{name}.json')
        if os.path.isfile(meta_path):
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                files = meta.get('installed_files', []) or []
                new_files = []
                for rel in files:
                    if isinstance(rel, str) and rel.startswith('plugins/') and '/' not in rel[len('plugins/'):]:
                        new_files.append(f'plugins/{name}/{os.path.basename(rel)}')
                    else:
                        new_files.append(rel)
                meta['installed_files'] = new_files
                with open(meta_path, 'w', encoding='utf-8') as f:
                    json.dump(meta, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"  警告：更新 installed_files 失败: {e}")
        print(f"  完成 -> plugins/{name}/（已生成 __init__.py）")
        return 0
    except Exception as e:
        print(f"  失败：{e}")
        return 1


def main() -> int:
    ap = argparse.ArgumentParser(description='旧扁平插件布局迁移到目录化自包含布局')
    ap.add_argument('--base', default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    help='框架根（默认本脚本上级目录）')
    ap.add_argument('--plugin', default='', help='仅迁移指定插件（默认全部非内置扁平插件）')
    ap.add_argument('--dry-run', action='store_true', help='仅预览迁移计划，不落盘')
    args = ap.parse_args()

    names = [args.plugin] if args.plugin else _find_plugins(args.base)
    if not names:
        print("未发现待迁移的扁平插件（或已是目录化布局）。")
        return 0
    mode = 'DRY-RUN（仅预览）' if args.dry_run else '执行'
    print(f"{mode}：框架根 {args.base}，待迁移插件 {len(names)} 个: {', '.join(names)}")
    print("（内置插件 auth/user_manage 已跳过）")
    fail = 0
    for n in names:
        fail += migrate_plugin(args.base, n, args.dry_run)
    print(f"迁移{'完成' if not args.dry_run else '预览'}结束，失败 {fail} 项。")
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
