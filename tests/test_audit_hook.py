# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""运行时审计钩子回归（v4.4.0，安全强化 P1 阶段三）

覆盖：
A. 事件映射：open 读写模式 / os.system / Popen / socket.connect·bind / sqlite3 / 删除族
B. 栈定位：plugins 帧来源识别 / 框架来源放行 / 嵌套调用归因 / 未知来源放行
C. observe 模式：未授权记录不阻断 / 授权无记录 / 隐式豁免无记录 / 聚合结构
D. enforce 模式：未授权阻断（异常传播）/ 授权放行 / 未注册 fail-closed / 审计落盘（flush_now）
E. 集成（隔离目录 + test client + 真实钩子）：插件 API 运行触发未授权聚合、
   /api/admin/stats 返回 audit_violations（按插件分组、无后端合计）、enforce 端到端阻断、
   建议声明与 cross_validate 同源一致、重载清零、真实项目未污染

运行：python tests/test_audit_hook.py
"""
import importlib.util
import io
import json
import os
import shutil
import socket
import sys
import tempfile
import zipfile

REAL_BASE = _PROJECT_ROOT
sys.path.insert(0, REAL_BASE)

import global_var
from core import capabilities as C
from core import audit_hook as AH

results = []

def check(name, cond, detail=''):
    results.append((name, cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

# ============ A：事件映射（私有 mapper 单元） ============
check("A1 open 写模式判定", AH._open_target(('p.txt', 'w', 0)) == ('filesystem:write', 'p.txt'))
check("A2 open 读模式判定", AH._open_target(('p.txt', 'r', 0)) == ('filesystem:read', 'p.txt'))
check("A3 open flags 模式判定（O_WRONLY）",
      AH._open_target(('p.txt', None, os.O_WRONLY))[0] == 'filesystem:write')
check("A4 os.system → process", AH._system_target(('cmd /c dir',)) == ('process:exec', ''))
check("A5 Popen 提取可执行名",
      AH._popen_target(('C:/bin/ffmpeg.exe', ['ffmpeg', '-i'], None, None)) == ('process:exec', 'ffmpeg.exe'))
check("A6 socket.connect 目标", AH._connect_target((('evil.com', 443),)) == ('network:tcp', 'tcp://evil.com:443'))
check("A7 socket.bind → server", AH._bind_target((('0.0.0.0', 8080),)) == ('network:server', ''))
check("A8 sqlite3 目标", AH._sqlite_target(('data/c.db', 5.0)) == ('database:sqlite', 'data/c.db'))
check("A9 删除族算写", AH._path_target(('C:/x/y.txt',)) == ('filesystem:write', 'C:/x/y.txt'))

# ============ B：栈定位（真实 plugins/ 帧） ============
_attr_dir = tempfile.mkdtemp(prefix='ftk_attr_')
os.makedirs(os.path.join(_attr_dir, 'plugins'), exist_ok=True)
_attr_mod = os.path.join(_attr_dir, 'plugins', 'attr_demo.py')
with open(_attr_mod, 'w', encoding='utf-8') as f:
    f.write('''# -*- coding: utf-8 -*-
from core import audit_hook as _ah

def who():
    return _ah._locate_plugin()

def nested():
    return _util_helper()

def _util_helper():
    return _ah._locate_plugin()
''')
_spec = importlib.util.spec_from_file_location('attr_demo_mod', _attr_mod)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
check("B1 plugins 帧识别", _mod.who() == 'attr_demo', f"got={_mod.who()}")
check("B2 框架来源放行（tests/ 帧）", AH._locate_plugin() is None)
check("B3 嵌套调用（插件→工具函数）归因", _mod.nested() == 'attr_demo', f"got={_mod.nested()}")

# ============ C：observe 模式（mock 归因，直接分派；不装真钩子） ============
_orig_locate = AH._locate_plugin
AH._MODE = 'observe'
AH._locate_plugin = lambda: 'auditdemo'  # type: ignore
C.register_capabilities('auditdemo', [
    f'filesystem:write:{tempfile.gettempdir().replace(chr(92), "/")}/auditdemo/',
    'network:tcp:127.0.0.1',
])
AH.clear_violations()
AH._handler('open', (os.path.join(tempfile.gettempdir(), 'evil.txt'), 'w', 0))
v = AH.get_violations()
writes = [d for d in v[0]['details'] if d['capability'].startswith('filesystem:write:')] if v else []
check("C1 未授权写聚合（插件分组）", len(v) == 1 and v[0]['plugin'] == 'auditdemo'
      and len(writes) == 1, str(v)[:100])
check("C2 建议声明为父目录级", bool(writes) and writes[0]['capability'].startswith('filesystem:write:')
      and writes[0]['capability'].endswith('/'), str(writes)[:80])
check("C3 事件样本可读", bool(writes) and 'evil.txt' in writes[0]['example'])
AH.clear_violations()
AH._handler('open', (os.path.join(tempfile.gettempdir(), 'auditdemo', 'out.txt'), 'w', 0))
check("C4 已声明路径无记录（observe 不阻断）", AH.get_violations() == [])
AH.clear_violations()
AH._handler('open', (os.path.join(global_var.BASE_DIR, 'plugins', 'data', 'auditdemo', 'v.json'), 'w', 0))
check("C5 自属路径隐式豁免无记录", AH.get_violations() == [])
AH.clear_violations()
AH._handler('socket.connect', (('127.0.0.1', 3306),))
check("C6 tcp 声明放行", AH.get_violations() == [])
AH._handler('socket.connect', (('evil.com', 443),))
v = AH.get_violations()
check("C7 未声明网络聚合（建议 tcp 去 scheme）",
      len(v) == 1 and v[0]['details'][0]['capability'] == 'network:tcp:evil.com:443', str(v)[:100])

# ============ D：enforce 模式 ============
AH._MODE = 'enforce'
AH.clear_violations()
try:
    AH._handler('socket.connect', (('evil.com', 443),))
    check("D1 enforce 未授权阻断", False)
except RuntimeError as e:
    check("D1 enforce 未授权阻断", '审计拒绝' in str(e) and 'auditdemo' in str(e))
AH.clear_violations()
try:
    AH._handler('open', (os.path.join(tempfile.gettempdir(), 'auditdemo', 'ok.txt'), 'w', 0))
    check("D2 enforce 授权放行", True)
except RuntimeError:
    check("D2 enforce 授权放行", False)
AH.clear_violations()
try:
    AH._handler('open', (os.path.join(global_var.BASE_DIR, 'plugins', 'data', 'auditdemo', 'v2.json'), 'w', 0))
    check("D3 enforce 自属路径放行", True)
except RuntimeError:
    check("D3 enforce 自属路径放行", False)
AH.clear_violations()
C.unregister_capabilities('ghost')
AH._locate_plugin = lambda: 'ghost'  # type: ignore
try:
    AH._handler('open', ('C:/x.txt', 'r', 0))
    check("D4 未注册插件 fail-closed", False)
except RuntimeError:
    check("D4 未注册插件 fail-closed", True)
AH._locate_plugin = lambda: 'auditdemo'  # type: ignore
# D5：未授权记录进入待落盘队列（真实文件落盘由 E11 在隔离目录验证）
AH._MODE = 'observe'
AH.clear_violations()
AH._handler('socket.connect', (('evil.com', 443),))
with AH._PENDING_LOCK:
    has_pending = any('auditdemo' in d for _, p, _, d in AH._PENDING)
check("D5 未授权记录进入待落盘队列", has_pending)
AH._MODE = 'observe'
AH._locate_plugin = _orig_locate  # 还原真实栈归因（E 组开始使用真实钩子）

# ============ E：集成（隔离目录 + 真实钩子） ============
_tmp = tempfile.mkdtemp(prefix='ftk_audit_')
_isolated = tempfile.mkdtemp(prefix='ftk_auditapi_')
for sub in ('plugins', 'temp', 'logs', 'data'):
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
_saved_scan = global_var.PLUGIN_SCAN_MODE
global_var.PLUGIN_SCAN_MODE = 'report'

import app as appmod
from core.plugin_loader import load_plugins
app = appmod.app
app.config["TESTING"] = True
load_plugins()

# 在隔离环境安装真实钩子（BASE_DIR 已指向隔离目录，审计落盘不污染真实项目）
AH.install_audit_hook('observe')
AH.flush_now()  # 清空单元测试期残留的待落盘队列
AH.clear_violations()

client = app.test_client()
_TEMP = tempfile.gettempdir().replace(chr(92), '/')

# 构造审计演示插件（真实 API 路由）
_audit_py = f'''# -*- coding: utf-8 -*-
import os, json, socket
from plugins.base_plugin import BasePlugin

class AuditdemoPlugin(BasePlugin):
    name = "auditdemo"
    title = "t"
    description = "d"
    version = "1.0.0"
    author = "t"
    category = "测试"
    @property
    def routes(self):
        return [
            {{"path": "/evil", "name": "evil", "methods": ["GET"], "params": [],
              "view_func": self.api_evil}},
            {{"path": "/good", "name": "good", "methods": ["GET"], "params": [],
              "view_func": self.api_good}},
            {{"path": "/selfdata", "name": "selfdata", "methods": ["GET"], "params": [],
              "view_func": self.api_selfdata}},
            {{"path": "/net-ok", "name": "net-ok", "methods": ["GET"], "params": [],
              "view_func": self.api_net_ok}},
            {{"path": "/net-bad", "name": "net-bad", "methods": ["GET"], "params": [],
              "view_func": self.api_net_bad}},
        ]
    def api_evil(self):
        with open(os.path.join(os.environ.get("TEMP", "."), "audit_hook_evil.txt"), "w") as f:
            f.write("x")
        return self.success_response(data={{"ok": True}})
    def api_good(self):
        d = os.path.join(os.environ.get("TEMP", "."), "auditdemo")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "out.txt"), "w") as f:
            f.write("x")
        return self.success_response(data={{"ok": True}})
    def api_selfdata(self):
        with open(self.get_data_path("visits.json"), "w") as f:
            f.write("{{}}")
        return self.success_response(data={{"ok": True}})
    def api_net_ok(self):
        s = socket.socket()
        try:
            s.connect(("127.0.0.1", 1))
        except OSError:
            pass
        finally:
            s.close()
        return self.success_response(data={{"ok": True}})
    def api_net_bad(self):
        s = socket.socket()
        try:
            s.connect(("10.255.255.1", 1))  # 保留地址：触发 connect 事件但快速失败（不依赖 DNS）
        except OSError:
            pass
        finally:
            s.close()
        return self.success_response(data={{"ok": True}})
'''
_audit_zip = os.path.join(_tmp, 'auditdemo.zip')
with zipfile.ZipFile(_audit_zip, 'w') as zf:
    zf.writestr('plugin.json', json.dumps({
        'name': 'auditdemo', 'version': '1.0.0',
        'capabilities': [f'filesystem:write:{_TEMP}/auditdemo/',
                         'network:tcp:127.0.0.1'],
    }))
    zf.writestr('auditdemo.py', _audit_py)
with io.open(_audit_zip, 'rb') as f:
    r = client.post('/api/admin/plugins/upload', data={'file': (f, 'auditdemo.zip', 'application/zip')},
                    content_type='multipart/form-data')
check("E1 审计演示插件安装成功", r.status_code == 200, f"status={r.status_code} msg={(r.get_json() or {}).get('message', '')[:60]}")

# E2：good（声明路径）无写/网络违规（解释器内部读噪音忽略）
AH.clear_violations()
r = client.get('/api/auditdemo/good')
v = AH.get_violations()
noise = [d for p in v for d in p['details']
         if d['capability'].startswith('filesystem:read:') and '__pycache__' in d['example']]
real = [d for p in v for d in p['details']
        if d['capability'].startswith(('filesystem:write:', 'network:'))]
check("E2 已声明写放行（observe 无违规）", r.status_code == 200 and not real, f"v={str(v)[:140]}")

# E3：selfdata（隐式豁免）无写/网络违规
AH.clear_violations()
r = client.get('/api/auditdemo/selfdata')
v = AH.get_violations()
real = [d for p in v for d in p['details']
        if d['capability'].startswith(('filesystem:write:', 'network:'))]
check("E3 自属 data 隐式豁免（真实钩子+栈归因）", r.status_code == 200 and not real,
      f"status={r.status_code} v={str(v)[:140]}")

# E4：evil（未声明）真实栈归因聚合
AH.clear_violations()
r = client.get('/api/auditdemo/evil')
v = AH.get_violations()
writes = [d for d in v[0]['details'] if d['capability'].startswith('filesystem:write:')] if v else []
check("E4 真实钩子+栈归因：未授权写聚合",
      r.status_code == 200 and len(v) == 1 and v[0]['plugin'] == 'auditdemo'
      and len(writes) >= 1, f"status={r.status_code} v={str(v)[:140]}")

# E5：net-bad 网络防火墙（未声明端点）
AH.clear_violations()
r = client.get('/api/auditdemo/net-bad')
v = AH.get_violations()
nets = [d for d in v[0]['details'] if d['capability'].startswith('network:tcp:')] if v else []
check("E5 网络白名单：未声明端点聚合", r.status_code == 200 and len(nets) == 1
      and nets[0]['capability'] == 'network:tcp:10.255.255.1:1', f"v={str(v)[:140]}")

# E6：/api/admin/stats 返回按插件分组、无后端合计
r = client.get('/api/admin/stats')
body = r.get_json() or {}
av = (body.get('data') or {}).get('audit_violations') or []
check("E6 stats 返回 audit_violations 按插件分组、无合计字段",
      isinstance(av, list) and any(p['plugin'] == 'auditdemo' for p in av)
      and 'total' in av[0] and not any('grand_total' in d or 'summary' in d for d in [body.get('data') or {}]),
      f"av={str(av)[:120]}")

# E7：enforce 端到端（真实钩子阻断 → 500）
AH._MODE = 'enforce'
AH.clear_violations()
r = client.get('/api/auditdemo/evil')
check("E7 enforce 端到端阻断（RuntimeError→500）", r.status_code == 500, f"status={r.status_code}")
r = client.get('/api/auditdemo/good')
check("E8 enforce 已声明路径放行", r.status_code == 200, f"status={r.status_code}")
r = client.get('/api/auditdemo/net-ok')
check("E9 enforce tcp 声明放行", r.status_code == 200, f"status={r.status_code}")
AH._MODE = 'observe'

# E10：重载清零（loader clear_violations）
load_plugins()
check("E10 插件重载后聚合清零", AH.get_violations() == [], f"v={AH.get_violations()}")

# E11：审计落盘于隔离目录（flush_now）
AH.clear_violations()
client.get('/api/auditdemo/evil')
AH.flush_now()
_iso_audit = os.path.join(_isolated, 'data', 'audit.log')
_iso_text = ''
if os.path.exists(_iso_audit):
    with open(_iso_audit, encoding='utf-8') as f:
        _iso_text = f.read()
check("E11 审计 JSONL 落盘隔离目录（含插件与建议声明）",
      'auditdemo' in _iso_text and 'filesystem:write' in _iso_text)

# E12：真实项目未污染
check("E12 真实项目未污染",
      not os.path.isfile(os.path.join(REAL_BASE, 'plugins', 'auditdemo.py'))
      and not os.path.isfile(os.path.join(REAL_BASE, 'data', 'audit.log')))

# ============ 汇总 ============
n_pass = sum(1 for _, c in results if c)
n_fail = len(results) - n_pass
print(f"\n==== 运行时审计钩子回归（v4.4.0）：共 {len(results)} 项，通过 {n_pass}，失败 {n_fail} ====")
sys.exit(1 if n_fail else 0)
