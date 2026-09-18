# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""tools/package.py 非 src_layout 打包排除 __pycache__/pyc 专项（v4.21.1）

背景：tools/package.py cmd_pack 的非 src_layout 分支（标准插件包结构）此前用
普通 os.walk 收集全部文件，未应用 src_layout 分支的 skip_dirs，导致 __pycache__/
下的 .pyc/.pyo 混入分发包。本测试固化修复：非 src_layout 分支须排除
__pycache__ 目录与 .pyc/.pyo 文件。

覆盖：
A. _collect_plain（辅助）或 cmd_pack 非 src_layout 分支产物不含 __pycache__/.pyc/.pyo
B. 正常成员（plugin.json + 主 .py + 辅助 .py + templates/）仍全部进包
C. 产物可被 parse_plugin_pack 解析

运行：python tests/test_pack_no_pyc.py
"""
import argparse
import io
import json
import os
import shutil
import sys
import tempfile
import zipfile
import importlib.util

sys.path.insert(0, _PROJECT_ROOT)

# 加载 tools/package.py（允许直接运行，不触发 __main__）
_spec = importlib.util.spec_from_file_location(
    'ftk_pack_no_pyc', os.path.join(_PROJECT_ROOT, 'tools', 'package.py'))
pkg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pkg)

from core.plugin_pack import parse_plugin_pack

results = []

def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

PLAIN_PY = '''from plugins.base_plugin import BasePlugin

class DemoPlainPlugin(BasePlugin):
    name = "demo_plain"
    version = "1.0.0"
    title = "标准插件包"
    author = "System"
    category = "系统管理"
    description = "非 src_layout 打包排除 pyc 测试插件"
    permission = "user"
    dependencies = []

    @property
    def routes(self):
        return []
'''

def build_plain(root):
    """标准插件包结构：plugin.json + <name>.py + 辅助 .py + templates/ + __pycache__/ + configs/ + tests/"""
    os.makedirs(os.path.join(root, 'templates'))
    os.makedirs(os.path.join(root, '__pycache__'))
    os.makedirs(os.path.join(root, 'configs'))
    os.makedirs(os.path.join(root, 'tests'))
    with io.open(os.path.join(root, 'plugin.json'), 'w', encoding='utf-8') as f:
        json.dump({'name': 'demo_plain', 'version': '1.0.0', 'title': '标准插件包',
                   'author': 'System', 'category': '系统管理',
                   'description': '非 src_layout 打包排除 pyc 测试插件',
                   'permission': 'user', 'dependencies': []}, f, ensure_ascii=False)
    with io.open(os.path.join(root, 'demo_plain.py'), 'w', encoding='utf-8') as f:
        f.write(PLAIN_PY)
    with io.open(os.path.join(root, 'helper.py'), 'w', encoding='utf-8') as f:
        f.write('HELPER = 1\n')
    with io.open(os.path.join(root, 'templates', 'index.html'), 'w', encoding='utf-8') as f:
        f.write('<html>plain index</html>')
    # 模拟 py_compile 产物
    with io.open(os.path.join(root, '__pycache__', 'demo_plain.cpython-311.pyc'), 'wb') as f:
        f.write(b'PYC1')
    with io.open(os.path.join(root, '__pycache__', 'helper.cpython-311.pyo'), 'wb') as f:
        f.write(b'PYC2')
    # 不应打包的目录（与 src_layout 进包策略对齐）：configs/（配置样例）+ tests/（测试）
    with io.open(os.path.join(root, 'configs', 'demo_plain.json'), 'w', encoding='utf-8') as f:
        f.write('{}')
    with io.open(os.path.join(root, 'tests', 'test_demo.py'), 'w', encoding='utf-8') as f:
        f.write('def test(): pass\n')

tmp = tempfile.mkdtemp(prefix='ftk_pack_no_pyc_')
src = os.path.join(tmp, 'src')
build_plain(src)

# ---------- cmd_pack 非 src_layout 分支打包 ----------
out_zip = os.path.join(tmp, 'out.zip')
args = argparse.Namespace(src_dir=src, output=out_zip, type='backend',
                          sign=None, signer='', src_layout='')
pkg.cmd_pack(args)
with zipfile.ZipFile(out_zip, 'r') as zf:
    names = set(n for n in zf.namelist() if not n.endswith('/'))

# A：排除 pyc/pyo 污染
check("A1 不含 __pycache__ 条目", not any(n.startswith('__pycache__/') for n in names),
      f"names={sorted(names)}")
check("A2 不含 .pyc/.pyo 文件", not any(n.endswith(('.pyc', '.pyo')) for n in names))

# B：正常成员全部进包
check("B1 plugin.json 进包", 'plugin.json' in names)
check("B2 主 .py 进包", 'demo_plain.py' in names)
check("B3 辅助 .py 进包", 'helper.py' in names)
check("B4 templates/ 进包", 'templates/index.html' in names)
check("B5 manifest.json 生成且文件数正确",
      'manifest.json' in names and len(names - {'manifest.json'}) == 4,
      f"count={len(names)} names={sorted(names)}")
check("B6 configs/ 不打包（与 src_layout 对齐）", not any(n.startswith('configs/') for n in names))
check("B7 tests/ 不打包（与 src_layout 对齐）", not any(n.startswith('tests/') for n in names))

# C：产物可被 parse_plugin_pack 解析
desc = parse_plugin_pack(out_zip)
check("C1 非 src_layout 包可 parse 对齐",
      desc.get('name') == 'demo_plain' and desc.get('version') == '1.0.0'
      and desc.get('permission') == 'user',
      f"name={desc.get('name')} version={desc.get('version')}")

# 清理
shutil.rmtree(tmp, ignore_errors=True)

passed = sum(1 for _, c, _ in results if c)
print(f"\n==== 非 src_layout 打包排除 pyc：共 {len(results)} 项，通过 {passed}，失败 {len(results) - passed} ====")
sys.exit(0 if passed == len(results) else 1)
