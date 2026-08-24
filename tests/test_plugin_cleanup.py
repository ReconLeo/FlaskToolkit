# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""插件包卸载清单（installed_files）专项回归
隔离 /tmp 目录 + 纯函数级调用，不启动服务、不污染真实项目。

覆盖：
- 多 .py 插件包安装时 installed_files 清单完整写入描述文件
- 卸载按清单全清（主 .py + 辅助模块 + 模板 + 描述文件），无残留
- 卸载后空目录清理
- clean_old 更新场景：先按旧清单删除旧版本引入的文件（避免 update 残留）
- 边界：installed_files 被手工篡改注入越界路径（../、绝对路径）时安全跳过，不越界删除
运行：python tests/test_plugin_cleanup.py
"""
import json
import os
import shutil
import sys
import tempfile
import zipfile

import global_var
from core.plugin_pack import extract_plugin_pack, cleanup_plugin_resources, _delete_installed_files

passed = failed = 0


def check(name, cond, extra=''):
    global passed, failed
    if cond:
        passed += 1
        print(f'[PASS] {name}')
    else:
        failed += 1
        print(f'[FAIL] {name} {extra}')


def build_pack(tmp, name, version, extra_pys=None, templates=None):
    """构造插件包目录并打包为 zip；extra_pys: 附加辅助模块名列表；templates: 模板相对路径列表"""
    pkg = os.path.join(tmp, f'{name}_src')
    if os.path.isdir(pkg):
        shutil.rmtree(pkg)  # 重建源目录，避免上次打包残留文件混入
    os.makedirs(pkg, exist_ok=True)
    if templates:
        for t in templates:
            os.makedirs(os.path.join(pkg, 'templates'), exist_ok=True)
    desc = {
        "name": name, "title": name, "version": version,
        "author": "t", "category": "示例", "description": name,
    }
    with open(os.path.join(pkg, 'plugin.json'), 'w', encoding='utf-8') as f:
        json.dump(desc, f, ensure_ascii=False)
    with open(os.path.join(pkg, f'{name}.py'), 'w', encoding='utf-8') as f:
        f.write(f"# main\nclass {name.capitalize()}:\n    name='{name}'\n    version='{version}'\n")
    for ep in (extra_pys or []):
        with open(os.path.join(pkg, f'{ep}.py'), 'w', encoding='utf-8') as f:
            f.write(f"# helper {ep}\n")
    for t in (templates or []):
        os.makedirs(os.path.join(pkg, 'templates'), exist_ok=True)
        with open(os.path.join(pkg, 'templates', t), 'w', encoding='utf-8') as f:
            f.write(f"<html>{t}</html>")

    zip_path = os.path.join(tmp, f'{name}-v{version}.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _d, files in os.walk(pkg):
            for fn in files:
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, pkg).replace('\\', '/')
                zf.write(full, rel)
    return zip_path


def main():
    TMP = tempfile.mkdtemp(prefix='ftk_cleanup_')
    BASE = os.path.join(TMP, 'project')
    for sub in ('plugins', 'templates/plugins', 'plugins/configs'):
        os.makedirs(os.path.join(BASE, sub), exist_ok=True)
    # 隔离环境：mock 到 /tmp（沙箱对 /tmp 放行，可执行真实删除）
    global_var.BASE_DIR = BASE
    global_var.PLUGIN_CONFIGS_DIR = os.path.join(BASE, 'plugins', 'configs')

    try:
        # ---------- 1. 多 .py 插件包安装 → installed_files 清单 ----------
        zip_path = build_pack(TMP, 'multi_plugin', '1.0.0',
                              extra_pys=['helper_a', 'helper_b'], templates=['multi_plugin.html'])
        result = extract_plugin_pack(zip_path, 'multi_plugin', meta_override={
            "name": "multi_plugin", "title": "多文件示例", "version": "1.0.0",
            "author": "t", "category": "示例", "description": "多文件插件包"})
        check('安装后主 .py 存在', os.path.isfile(os.path.join(BASE, 'plugins', 'multi_plugin.py')))
        check('安装后辅助模块 helper_a 存在', os.path.isfile(os.path.join(BASE, 'plugins', 'helper_a.py')))
        check('安装后辅助模块 helper_b 存在', os.path.isfile(os.path.join(BASE, 'plugins', 'helper_b.py')))
        check('安装后模板存在', os.path.isfile(os.path.join(BASE, 'templates', 'plugins', 'multi_plugin.html')))
        check('py 清单含 3 个模块', len(result['py']) == 3, str(result['py']))

        meta_file = os.path.join(BASE, 'plugins', 'multi_plugin.json')
        meta = json.load(open(meta_file, encoding='utf-8'))
        check('描述文件写入 installed_files', isinstance(meta.get('installed_files'), list))
        installed = meta.get('installed_files', [])
        expect = {
            'plugins/multi_plugin.py', 'plugins/helper_a.py', 'plugins/helper_b.py',
            'plugins/multi_plugin.json', 'templates/plugins/multi_plugin.html',
        }
        check('installed_files 清单完整', set(installed) == expect, str(installed))

        # ---------- 2. 卸载按清单全清 ----------
        removed = cleanup_plugin_resources('multi_plugin')
        check('卸载后主 .py 已删', not os.path.exists(os.path.join(BASE, 'plugins', 'multi_plugin.py')))
        check('卸载后 helper_a 已删', not os.path.exists(os.path.join(BASE, 'plugins', 'helper_a.py')))
        check('卸载后 helper_b 已删', not os.path.exists(os.path.join(BASE, 'plugins', 'helper_b.py')))
        check('卸载后模板已删', not os.path.exists(os.path.join(BASE, 'templates', 'plugins', 'multi_plugin.html')))
        check('卸载后描述文件已删', not os.path.exists(meta_file))
        check('卸载删除路径数 >= 5', len(removed) >= 5, str(removed))

        tpl_plugins = os.path.join(BASE, 'templates', 'plugins')
        if os.path.isdir(tpl_plugins):
            left = [x for x in os.listdir(tpl_plugins) if x not in ('static',)]
            check('templates/plugins 下无残留非 static 项', left == [], str(left))
        else:
            check('templates/plugins 空目录已被清理', True)

        # ---------- 3. clean_old：更新时按旧清单清理旧版本引入文件 ----------
        # v1 含 helper_a/helper_b
        z1 = build_pack(TMP, 'upd_plugin', '1.0.0', extra_pys=['helper_a', 'helper_b'])
        extract_plugin_pack(z1, 'upd_plugin', meta_override={"name": "upd_plugin", "version": "1.0.0"})
        check('v1 安装后 helper_a 存在', os.path.isfile(os.path.join(BASE, 'plugins', 'helper_a.py')))
        # v2 不再携带 helper_a（模拟新版本移除辅助模块）→ clean_old=True 应清掉旧 helper_a
        z2 = build_pack(TMP, 'upd_plugin', '1.0.1', extra_pys=['helper_b'])
        extract_plugin_pack(z2, 'upd_plugin', meta_override={"name": "upd_plugin", "version": "1.0.1"})
        check('v2 更新后旧 helper_a 已清理', not os.path.exists(os.path.join(BASE, 'plugins', 'helper_a.py')))
        check('v2 更新后新 helper_b 保留', os.path.isfile(os.path.join(BASE, 'plugins', 'helper_b.py')))
        check('v2 清单更新为不含 helper_a',
              'plugins/helper_a.py' not in json.load(open(meta_file.replace('multi', 'upd'), encoding='utf-8')).get('installed_files', []),
              str(json.load(open(meta_file.replace('multi', 'upd'), encoding='utf-8')).get('installed_files', [])))
        cleanup_plugin_resources('upd_plugin')

        # ---------- 4. 边界：installed_files 被手工篡改注入越界路径 ----------
        # 在项目外放置一个文件，篡改描述文件清单指向它，验证不越界删除
        outside = os.path.join(TMP, 'outside_target.txt')
        with open(outside, 'w', encoding='utf-8') as f:
            f.write('must survive')
        meta_bad = os.path.join(BASE, 'plugins', 'evil.json')
        with open(meta_bad, 'w', encoding='utf-8') as f:
            json.dump({'name': 'evil', 'version': '1.0.0',
                       'installed_files': ['plugins/evil.json', '../outside_target.txt', 'plugins/evil.py',
                                           os.path.abspath(outside), 'plugins/../../data/stats.json']}, f, ensure_ascii=False)
        # 一个项目内合法文件 + 一个清单外文件，验证按清单删除、不越界、不误删
        with open(os.path.join(BASE, 'plugins', 'evil.py'), 'w', encoding='utf-8') as f:
            f.write('# evil')
        with open(os.path.join(BASE, 'plugins', 'unlisted.py'), 'w', encoding='utf-8') as f:
            f.write('# unlisted')
        removed = cleanup_plugin_resources('evil')
        check('越界 ../ 路径被安全跳过', os.path.exists(outside), outside)
        check('项目外绝对路径被跳过', os.path.exists(outside), outside)
        check('项目内合法清单文件被删除', not os.path.exists(os.path.join(BASE, 'plugins', 'evil.py')))
        check('清单内 meta 自身被删除', not os.path.exists(meta_bad))
        check('清单外文件不被误删', os.path.exists(os.path.join(BASE, 'plugins', 'unlisted.py')))

        print(f'\n==== 插件卸载清单回归：通过 {passed}，失败 {failed} ====')
    finally:
        try:
            shutil.rmtree(TMP, ignore_errors=True)
        except Exception:
            pass

    sys.exit(0 if failed == 0 else 1)


if __name__ == '__main__':
    main()
