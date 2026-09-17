# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""插件包描述一致性（plugin.json vs 插件类属性）对齐专项单元测试

规则（v4.1）：
1. plugin.json 与主 .py 文件名、类 name 三处一致（AST 可提取时）
2. 冲突字段（version/title/author/permission/category/description/dependencies）→ 拒绝并报告
3. plugin.json 缺失字段 → 类属性兜底补齐；落盘为对齐后的权威描述

运行：python test_pack_meta.py（不依赖 Flask 服务）
"""
import json
import os
import shutil
import sys
import tempfile
import zipfile

sys.path.insert(0, _PROJECT_ROOT)

import global_var
from core.plugin_pack import parse_plugin_pack, extract_plugin_pack

results = []


def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")


class TmpBase:
    """临时项目根：mock global_var.BASE_DIR"""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix='packmeta_')
        self._old = None

    def __enter__(self):
        self._old = global_var.BASE_DIR
        global_var.BASE_DIR = self.root
        return self.root

    def __exit__(self, *exc):
        global_var.BASE_DIR = self._old
        try:
            shutil.rmtree(self.root, ignore_errors=True)
        except Exception:
            pass


GOOD_PY = '''
from plugins.base_plugin import BasePlugin

class UserManagePlugin(BasePlugin):
    name = "user_manage"
    version = "1.0.1"
    title = "用户账号管理"
    author = "System"
    category = "系统管理"
    description = "用户账号管理插件"
    permission = "admin"
    dependencies = ["auth"]
'''

GOOD_JSON = {
    "name": "user_manage",
    "version": "1.0.1",
    "title": "用户账号管理",
    "author": "System",
    "category": "系统管理",
    "description": "用户账号管理插件",
    "permission": "admin",
    "dependencies": ["auth"],
}


PIP_PY = '''
from plugins.base_plugin import BasePlugin

class UserManagePlugin(BasePlugin):
    name = "user_manage"
    version = "1.0.1"
    title = "用户账号管理"
    author = "System"
    category = "系统管理"
    description = "用户账号管理插件"
    permission = "admin"
    dependencies = ["auth"]
    pip_dependencies = ["requests>=2.28", "cryptography"]
'''

def make_zip(path, json_obj, py_source, py_name='user_manage.py'):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('plugin.json', json.dumps(json_obj, ensure_ascii=False).encode('utf-8'))
        zf.writestr(py_name, py_source)
def expect_ok(label, json_obj, py_source, py_name='user_manage.py'):
    """期望解析成功，返回对齐后的 desc"""
    with TmpBase() as root:
        zp = os.path.join(root, 'p.zip')
        make_zip(zp, json_obj, py_source, py_name)
        try:
            desc = parse_plugin_pack(zp)
            check(label, True, f"desc={desc}")
            return desc
        except ValueError as e:
            check(label, False, f"意外拒绝: {e}")
            return None


def expect_reject(label, json_obj, py_source, py_name='user_manage.py', keyword=''):
    """期望解析被拒绝（ValueError）"""
    with TmpBase() as root:
        zp = os.path.join(root, 'p.zip')
        make_zip(zp, json_obj, py_source, py_name)
        try:
            parse_plugin_pack(zp)
            check(label, False, '未抛异常')
        except ValueError as e:
            ok = (keyword in str(e)) if keyword else True
            check(label, ok, str(e)[:60])


def test_alignment():
    # 1. 完全一致 → 通过
    expect_ok('完全一致通过', dict(GOOD_JSON), GOOD_PY)

    # 2. plugin.json 缺 version → 类兜底
    d = dict(GOOD_JSON)
    del d['version']
    desc = expect_ok('plugin.json 缺 version 类兜底', d, GOOD_PY)
    if desc:
        check('version 已从类兜底', desc.get('version') == '1.0.1', f"version={desc.get('version')}")

    # 3. plugin.json 缺 dependencies → 类兜底
    d = dict(GOOD_JSON)
    del d['dependencies']
    desc = expect_ok('plugin.json 缺 dependencies 类兜底', d, GOOD_PY)
    if desc:
        check('dependencies 已从类兜底', desc.get('dependencies') == ['auth'], f"deps={desc.get('dependencies')}")

    # 4. plugin.json 缺多个展示字段 → 类兜底
    d = {'name': 'user_manage'}
    desc = expect_ok('plugin.json 仅 name 其余类兜底', d, GOOD_PY)
    if desc:
        ok = (desc.get('version') == '1.0.1' and desc.get('permission') == 'admin'
              and desc.get('dependencies') == ['auth'] and desc.get('title') == '用户账号管理')
        check('其余字段均已兜底', ok, f"desc={desc}")


def test_conflicts():
    # 5. version 冲突 → 拒绝
    d = dict(GOOD_JSON)
    d['version'] = '2.0.0'
    expect_reject('version 冲突拒绝', d, GOOD_PY, keyword='version')

    # 6. dependencies 冲突 → 拒绝
    d = dict(GOOD_JSON)
    d['dependencies'] = ['other_plugin']
    expect_reject('dependencies 冲突拒绝', d, GOOD_PY, keyword='dependencies')

    # 7. title 冲突 → 拒绝
    d = dict(GOOD_JSON)
    d['title'] = '其他标题'
    expect_reject('title 冲突拒绝', d, GOOD_PY, keyword='title')

    # 8. permission 冲突 → 拒绝
    d = dict(GOOD_JSON)
    d['permission'] = 'user'
    expect_reject('permission 冲突拒绝', d, GOOD_PY, keyword='permission')

    # 9. 多字段冲突 → 报告全部
    d = dict(GOOD_JSON)
    d['version'] = '2.0.0'
    d['author'] = 'Other'
    with TmpBase() as root:
        zp = os.path.join(root, 'p.zip')
        make_zip(zp, d, GOOD_PY)
        try:
            parse_plugin_pack(zp)
            check('多字段冲突报告', False, '未抛异常')
        except ValueError as e:
            msg = str(e)
            ok = 'version' in msg and 'author' in msg
            check('多字段冲突报告全部', ok, msg[:60])

    # 10. 冲突报错须附两处值（v4.17.2）：plugin.json 值 vs 类属性值
    d = dict(GOOD_JSON)
    d['version'] = '2.0.0'          # 类属性=1.0.1
    d['dependencies'] = ['other']   # 类属性=['auth']
    with TmpBase() as root:
        zp = os.path.join(root, 'p.zip')
        make_zip(zp, d, GOOD_PY)
        try:
            parse_plugin_pack(zp)
            check('冲突报错附两处值', False, '未抛异常')
        except ValueError as e:
            msg = str(e)
            ok = ("version" in msg and "2.0.0" in msg and "1.0.1" in msg
                  and "dependencies" in msg and "other" in msg and "auth" in msg)
            check('冲突报错附 plugin.json 值与类属性值', ok, msg[:120])


def test_name_consistency():
    # 10. 类 name 与 plugin.json name 不一致 → 拒绝
    bad_py = GOOD_PY.replace('name = "user_manage"', 'name = "other_name"')
    expect_reject('类 name 与 plugin.json 不一致拒绝', dict(GOOD_JSON), bad_py, keyword='name')

    # 11. 类 name 无法静态提取（如 __init__ 动态设置）→ 不误伤（跳过 name 校验）
    dynamic_py = '''
from plugins.base_plugin import BasePlugin

class DynamicPlugin(BasePlugin):
    version = "1.0.1"
    def __init__(self):
        super().__init__()
        self.name = "user_manage"
'''
    expect_ok('类 name 动态设置不误伤', dict(GOOD_JSON), dynamic_py)

    # 12. 主 .py 文件名与 plugin.json name 不一致 → 拒绝（parse 原校验）
    expect_reject('主 .py 文件名不匹配拒绝', dict(GOOD_JSON), GOOD_PY,
                  py_name='other.py', keyword='缺少主插件文件')


def test_extract_writes_aligned_meta():
    """落盘 plugins/<name>/<name>.json 为对齐后的描述（含类兜底字段，v4.21 目录化）"""
    with TmpBase() as root:
        zp = os.path.join(root, 'p.zip')
        # plugin.json 缺 version/dependencies，期望落盘时已补齐
        d = {'name': 'user_manage', 'title': '用户账号管理'}
        make_zip(zp, d, GOOD_PY)
        desc = parse_plugin_pack(zp)
        extract_plugin_pack(zp, 'user_manage', meta_override=desc)

        meta_path = os.path.join(root, 'plugins', 'user_manage', 'user_manage.json')
        check('描述文件已落盘(目录化 plugins/user_manage/user_manage.json)', os.path.isfile(meta_path), f"exists={os.path.isfile(meta_path)}")
        if os.path.isfile(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                landed = json.load(f)
            ok = (landed.get('version') == '1.0.1'
                  and landed.get('dependencies') == ['auth']
                  and landed.get('name') == 'user_manage')
            check('落盘描述已对齐补全', ok, f"landed={landed}")


def test_extract_locales_plugin_pack():
    """v4.21 插件语言包安装：locales/ 解压到 plugins/<name>/locales/ 并记入 installed_files
    （修复：extract_plugin_pack 曾把 locales/ 当未知条目忽略，导致插件 self.t() 翻译不生效）"""
    with TmpBase() as root:
        zp = os.path.join(root, 'p.zip')
        # 构造含 locales/ 的插件包
        with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('plugin.json', json.dumps(GOOD_JSON, ensure_ascii=False).encode('utf-8'))
            zf.writestr('user_manage.py', GOOD_PY)
            zf.writestr('locales/en.json', json.dumps({'用户账号管理': 'User Management'}, ensure_ascii=False).encode('utf-8'))
            zf.writestr('locales/fr.json', json.dumps({'用户账号管理': 'Gestion des utilisateurs'}, ensure_ascii=False).encode('utf-8'))
        desc = parse_plugin_pack(zp)
        res = extract_plugin_pack(zp, 'user_manage', meta_override=desc)

        # 1. locales 解压到 plugins/<name>/locales/
        en_p = os.path.join(root, 'plugins', 'user_manage', 'locales', 'en.json')
        fr_p = os.path.join(root, 'plugins', 'user_manage', 'locales', 'fr.json')
        check('插件语言包解压到 plugins/<name>/locales/en.json', os.path.isfile(en_p), f"exists={os.path.isfile(en_p)}")
        check('插件语言包解压到 plugins/<name>/locales/fr.json', os.path.isfile(fr_p), f"exists={os.path.isfile(fr_p)}")

        # 2. 返回结果 dict 含 locales 清单
        check('extract 返回 locales 清单', res.get('locales') == [en_p, fr_p], f"locales={res.get('locales')}")

        # 3. installed_files 记入 locales（供卸载/更新清理）
        with open(os.path.join(root, 'plugins', 'user_manage', 'user_manage.json'), encoding='utf-8') as f:
            landed = json.load(f)
        inst = [x for x in landed.get('installed_files', []) if 'locales' in x]
        check('installed_files 含 locales 条目',
              set(inst) == {'plugins/user_manage/locales/en.json', 'plugins/user_manage/locales/fr.json'},
              f"inst={inst}")

        # 4. 内容正确写入
        with open(en_p, encoding='utf-8') as f:
            d = json.load(f)
        check('语言包内容正确', d.get('用户账号管理') == 'User Management', f"d={d}")

def test_pip_dependencies():
    """pip_dependencies 字段：plugin.json 透传 / 类兜底 / 冲突拒绝（v4.10）"""
    with TmpBase() as root:
        # 1. plugin.json 声明 + 类一致 → 保留
        d = dict(GOOD_JSON)
        d['pip_dependencies'] = ["requests>=2.28", "cryptography"]
        desc = expect_ok('plugin.json 声明 pip_dependencies', d, PIP_PY)
        if desc:
            check('pip_dependencies 透传保留',
                  desc.get('pip_dependencies') == ["requests>=2.28", "cryptography"],
                  f"pip={desc.get('pip_dependencies')}")
        # 2. plugin.json 缺 pip_dependencies → 类兜底
        d2 = dict(GOOD_JSON)
        desc2 = expect_ok('plugin.json 缺 pip_dependencies 类兜底', d2, PIP_PY)
        if desc2:
            check('pip_dependencies 已从类兜底',
                  desc2.get('pip_dependencies') == ["requests>=2.28", "cryptography"],
                  f"pip={desc2.get('pip_dependencies')}")
        # 3. 两处冲突 → 拒绝
        d3 = dict(GOOD_JSON)
        d3['pip_dependencies'] = ["conflict_pkg"]
        expect_reject('pip_dependencies 冲突拒绝', d3, PIP_PY, keyword='pip_dependencies')

if __name__ == '__main__':
    test_alignment()
    test_conflicts()
    test_name_consistency()
    test_extract_writes_aligned_meta()
    test_extract_locales_plugin_pack()
    test_pip_dependencies()

    passed = sum(1 for _, c, _ in results if c)
    print(f"\n==== 描述一致性 共 {len(results)} 项，通过 {passed}，失败 {len(results) - passed} ====")
    sys.exit(0 if passed == len(results) else 1)
