# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""tools/package.py 源码布局自动映射专项（v4.17.2）

背景：AirDrop 采用「源码目录（<name>.json + <name>.py + frontend/）」与「分发包
（plugin.json + 主 .py + templates/static）」两套异构布局。v4.17.2 起 package.py
pack 支持 --src-layout 把源码布局自动映射为分发布局。

覆盖：
A. _src_to_dist / _collect_src_layout 映射规则（<name>.json→plugin.json、
   <name>.py 原样、frontend/*.html→templates/*.html、frontend/static/*→static/*、
   locales/* 保留、configs/ 与 __pycache__ 排除）
B. cmd_pack 打包产物成员符合分发布局
C. 打包产物可被 parse_plugin_pack 解析（描述一致性对齐）

运行：python tests/test_src_layout.py
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
    'ftk_package_tool', os.path.join(_PROJECT_ROOT, 'tools', 'package.py'))
pkg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pkg)

from core.plugin_pack import parse_plugin_pack

results = []

def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

# ---------- 源码布局样例（AirDrop 形态） ----------
SRC_PY = '''from plugins.base_plugin import BasePlugin

class AirdropSrcPlugin(BasePlugin):
    name = "airdrop_src"
    version = "1.1.0"
    title = "局域网文件共享"
    author = "AirDrop"
    category = "文件共享"
    description = "源码布局映射测试插件"
    permission = "user"
    dependencies = []

    @property
    def routes(self):
        return []
'''

def build_src(root):
    os.makedirs(os.path.join(root, 'frontend', 'static'))
    os.makedirs(os.path.join(root, 'locales'))
    os.makedirs(os.path.join(root, 'configs'))
    with io.open(os.path.join(root, 'airdrop_src.json'), 'w', encoding='utf-8') as f:
        json.dump({'name': 'airdrop_src', 'version': '1.1.0', 'title': '局域网文件共享',
                   'author': 'AirDrop', 'category': '文件共享',
                   'description': '源码布局映射测试插件', 'permission': 'user',
                   'dependencies': []}, f, ensure_ascii=False)
    with io.open(os.path.join(root, 'airdrop_src.py'), 'w', encoding='utf-8') as f:
        f.write(SRC_PY)
    with io.open(os.path.join(root, 'frontend', 'index.html'), 'w', encoding='utf-8') as f:
        f.write('<html>src index</html>')
    with io.open(os.path.join(root, 'frontend', 'static', 'qrcode.min.js'), 'w', encoding='utf-8') as f:
        f.write('var qrcode = {};')
    with io.open(os.path.join(root, 'locales', 'en.json'), 'w', encoding='utf-8') as f:
        f.write('{"hello": "hi"}')
    # 不打包：configs/（配置样例）+ __pycache__（产物）
    with io.open(os.path.join(root, 'configs', 'airdrop_src.json'), 'w', encoding='utf-8') as f:
        f.write('{}')
    os.makedirs(os.path.join(root, '__pycache__'))
    with io.open(os.path.join(root, '__pycache__', 'x.pyc'), 'wb') as f:
        f.write(b'PYC')

tmp = tempfile.mkdtemp(prefix='ftk_srclayout_')
src = os.path.join(tmp, 'src')
build_src(src)

# ---------- A：映射规则 ----------
flist, name = pkg._collect_src_layout(src)
zrel_set = {z for z, _ in flist}
check("A1 识别 name 从 <name>.py 主插件", name == 'airdrop_src', f"name={name}")
check("A2 描述 <name>.json -> plugin.json", 'plugin.json' in zrel_set)
check("A3 主 .py 原样保留", 'airdrop_src.py' in zrel_set)
check("A4 frontend/index.html -> templates/index.html", 'templates/index.html' in zrel_set)
check("A5 frontend/static/* -> static/*", 'static/qrcode.min.js' in zrel_set)
check("A6 locales/ 保留进包", 'locales/en.json' in zrel_set)
check("A7 configs/ 不打包", not any(z.startswith('configs/') for z in zrel_set))
check("A8 __pycache__ 不打包", not any(z.startswith('__pycache__') for z in zrel_set))
check("A9 文件总数正确", len(zrel_set) == 5, f"count={len(zrel_set)} members={sorted(zrel_set)}")

# ---------- B：cmd_pack 打包 ----------
out_zip = os.path.join(tmp, 'out.zip')
args = argparse.Namespace(src_dir=src, output=out_zip, type='backend',
                          sign=None, signer='', src_layout='backend')
pkg.cmd_pack(args)
with zipfile.ZipFile(out_zip, 'r') as zf:
    names = set(n for n in zf.namelist() if not n.endswith('/'))
    contents = {n: zf.read(n).decode('utf-8') for n in names}
check("B1 分发包成员含 plugin.json+主.py", 'plugin.json' in names and 'airdrop_src.py' in names)
check("B2 分发包成员含 templates/static", 'templates/index.html' in names and 'static/qrcode.min.js' in names)
check("B3 分发包不含 configs/__pycache__",
      not any(n.startswith('configs/') or n.startswith('__pycache__') for n in names))
check("B4 描述文件已映射为 plugin.json 且内容=源码描述",
      json.loads(contents['plugin.json']).get('name') == 'airdrop_src'
      and json.loads(contents['plugin.json']).get('version') == '1.1.0',
      f"plugin.json={contents.get('plugin.json', '')[:80]}")
check("B5 frontend/index.html 内容正确", 'src index' in contents.get('templates/index.html', ''))
check("B6 manifest.json 已生成", 'manifest.json' in names)

# ---------- C：parse_plugin_pack 可解析 ----------
desc = parse_plugin_pack(out_zip)
check("C1 源码布局包可 parse 对齐",
      desc.get('name') == 'airdrop_src' and desc.get('version') == '1.1.0'
      and desc.get('permission') == 'user', f"name={desc.get('name')} version={desc.get('version')}")

# 清理
shutil.rmtree(tmp, ignore_errors=True)

passed = sum(1 for _, c, _ in results if c)
print(f"\n==== 源码布局自动映射：共 {len(results)} 项，通过 {passed}，失败 {len(results) - passed} ====")
sys.exit(0 if passed == len(results) else 1)
