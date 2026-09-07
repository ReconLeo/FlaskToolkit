# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""v4.15 Root 域与市场骨架回归（framework 能力域 / 服务层权限 / 插件更新源）

覆盖：
A. plugin.json 新字段（repo/update_feed）解析与 META_FIELDS 透传
B. 安装门禁：framework:core 包 preview 的 framework_level 警示 + confirm 安装 + catalog 带 capabilities
C. 服务层权限：require_manage 显式 actor 判定（market 放行 / normal 抛 PluginAdminPermissionError）；
   install_from_package(actor=market) 成功 / (actor=normal) 拒绝且未落盘
D. 插件更新源：本地假 feed 拉取 + 版本比较 + 缓存命中 + 未声明 update_feed 返回空
E. framework:core 插件加载横幅（日志含 Root 权限字样）

运行：python tests/test_root_domain.py
"""
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import zipfile

REAL_BASE = _PROJECT_ROOT
sys.path.insert(0, REAL_BASE)

import global_var
from core import capabilities as C

# ------------------------------ 隔离目录（同 test_admin_api 模式） ------------------------------
_isolated = tempfile.mkdtemp(prefix='_iso_root415_')
os.makedirs(os.path.join(_isolated, 'plugins'))
os.makedirs(os.path.join(_isolated, 'temp'))
os.makedirs(os.path.join(_isolated, 'logs'))
shutil.copy(os.path.join(REAL_BASE, 'plugins', '__init__.py'),
            os.path.join(_isolated, 'plugins', '__init__.py'))
shutil.copy(os.path.join(REAL_BASE, 'plugins', 'base_plugin.py'),
            os.path.join(_isolated, 'plugins', 'base_plugin.py'))
sys.path.insert(0, _isolated)

_SAVED = {}
for attr, val in (('BASE_DIR', _isolated), ('UPLOAD_TEMP_DIR', os.path.join(_isolated, 'temp')),
                  ('LOG_DIR', os.path.join(_isolated, 'logs')),
                  ('PLUGIN_CONFIGS_DIR', os.path.join(_isolated, 'plugins', 'configs')),
                  ('FRONTEND_CONFIG_FILE', os.path.join(_isolated, 'frontend_tools.json')),
                  ('FRONTEND_TEMPLATE_DIR', os.path.join(_isolated, 'templates', 'frontend_tools')),
                  ('USER_CONFIG_FILE', os.path.join(_isolated, 'user_config.json')),
                  ('AUDIT_LOG_FILE', os.path.join(_isolated, 'audit.log')),
                  ('STATS_FILE', os.path.join(_isolated, 'stats.json'))):
    _SAVED[attr] = getattr(global_var, attr, None)
    setattr(global_var, attr, val)

import app as appmod
from core.plugin_loader import load_plugins

app = appmod.app
app.config["TESTING"] = True
load_plugins()  # 隔离目录无插件 → 游客放行

results = []


def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")


def build_plugin_zip(name, version, caps=None, repo='', update_feed=''):
    """构造后端插件包 zip（BytesIO）"""
    buf = io.BytesIO()
    desc = {'name': name, 'title': f'测试 {name}', 'version': version,
            'author': 'FT Tests', 'permission': 'user'}
    if caps:
        desc['capabilities'] = caps
    if repo:
        desc['repo'] = repo
    if update_feed:
        desc['update_feed'] = update_feed
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_STORED) as zf:
        zf.writestr('plugin.json', json.dumps(desc, ensure_ascii=False))
        zf.writestr(f'{name}.py', f'''# -*- coding: utf-8 -*-
from plugins.base_plugin import BasePlugin

class {name.title()}Plugin(BasePlugin):
    name = '{name}'
    title = '测试 {name}'
    version = '{version}'
    author = 'FT Tests'
    permission = 'user'

    @property
    def description(self):
        return 'v4.15 root 域测试插件'

    @property
    def category(self):
        return '测试'

    def routes(self):
        return []
''')
    buf.seek(0)
    return buf


# ------------------------------ A. plugin.json 新字段解析 ------------------------------
from core.plugin_pack import META_FIELDS, parse_plugin_pack

check("A1 META_FIELDS 含 repo/update_feed",
      'repo' in META_FIELDS and 'update_feed' in META_FIELDS, '')

_mkt = build_plugin_zip('market_tool', '1.0.0', ['framework:manage'],
                        repo='https://github.com/x/market_tool',
                        update_feed='http://127.0.0.1:9999/feed.json')
_tmp_pack = os.path.join(_isolated, 'temp', 'market_tool.zip')
with open(_tmp_pack, 'wb') as _f:
    _f.write(_mkt.getvalue())
_desc = parse_plugin_pack(_tmp_pack)
check("A2 parse_plugin_pack 保留 repo/update_feed",
      _desc.get('repo') == 'https://github.com/x/market_tool'
      and _desc.get('update_feed') == 'http://127.0.0.1:9999/feed.json',
      f"repo={_desc.get('repo')} feed={_desc.get('update_feed')}")

# ------------------------------ B. 安装门禁：framework 警示与安装 ------------------------------
_client = app.test_client()

def _upload_preview(buf, filename):
    return _client.post('/api/admin/plugins/upload',
                        data={'file': (buf, filename), 'preview': '1'},
                        content_type='multipart/form-data')

def _confirm_install(preview_id):
    return _client.post('/api/admin/plugins/upload',
                        data={'confirm': '1', 'preview_id': preview_id},
                        content_type='multipart/form-data')

_root = build_plugin_zip('rootdemo', '1.0.0', ['framework:core'])
_pv = _upload_preview(_root, 'rootdemo.zip')
_pvd = _pv.get_json() or {}
check("B1 framework:core preview → framework_level=core",
      _pv.status_code == 200 and _pvd.get('preview', {}).get('framework_level') == 'core',
      f"status={_pv.status_code} level={_pvd.get('preview', {}).get('framework_level')}")
_pid = _pvd.get('preview_id', '')
_cf = _confirm_install(_pid)
_cfd = _cf.get_json() or {}
check("B2 confirm 安装成功", _cf.status_code == 200 and _cfd.get('code') == 200,
      f"status={_cf.status_code} body={_cf.get_data(as_text=True)[:120]}")
check("B3 rootdemo 落盘", os.path.isfile(os.path.join(_isolated, 'plugins', 'rootdemo.py')), '')
_dbg_names = [p.get('name') for p in global_var.plugin_catalog]
check("B4 catalog 含 capabilities",
      any(p.get('name') == 'rootdemo' and 'framework:core' in (p.get('capabilities') or [])
          for p in global_var.plugin_catalog),
      f"caps={[p.get('capabilities') for p in global_var.plugin_catalog if p.get('name') == 'rootdemo']} "
      f"names={_dbg_names} json={os.path.isfile(os.path.join(_isolated, 'plugins', 'rootdemo.json'))}")

# filesystem:write 核心收紧：带 filesystem:write:core/ 声明的包 preview → cap errors（安装被拒）
_evil = build_plugin_zip('evilroot', '1.0.0', ['filesystem:write:core/network.py'])
_pve = _upload_preview(_evil, 'evilroot.zip')
_pved = _pve.get_json() or {}
_cap_raw = (_pved.get('preview', {}).get('capabilities') or [])
check("B5 preview 透传原始 capabilities（含 framework:core 收紧声明）",
      'filesystem:write:core/network.py' in _cap_raw,
      f"caps={_cap_raw}")

# ------------------------------ C. 服务层权限 ------------------------------
from core.plugin_admin import (PluginAdminPermissionError, install_from_package,
                               require_manage)
from core.capabilities import register_capabilities

register_capabilities('market_tool', ['framework:manage'])
register_capabilities('normal_plugin', [])

check("C1 require_manage(market) 放行", require_manage('market_tool') == 'market_tool', '')
try:
    require_manage('normal_plugin')
    check("C2 require_manage(normal) 拒绝", False, '未抛异常')
except PluginAdminPermissionError as _e:
    check("C2 require_manage(normal) 拒绝", 'framework:manage' in str(_e), str(_e))
try:
    require_manage('ghost_plugin')
    check("C3 require_manage(未注册) 拒绝", False, '未抛异常')
except PluginAdminPermissionError:
    check("C3 require_manage(未注册) 拒绝", True, '')

# 服务层安装：market 放行 / normal 拒绝且未落盘
_mkt2 = build_plugin_zip('service_inst', '1.0.0')
_tmp2 = os.path.join(_isolated, 'temp', 'service_inst.zip')
with open(_tmp2, 'wb') as _f:
    _f.write(_mkt2.getvalue())
ok1, msg1, _ = install_from_package(_tmp2, actor='market_tool')
check("C4 install_from_package(market) 成功", ok1, msg1)
check("C5 service_inst 落盘", os.path.isfile(os.path.join(_isolated, 'plugins', 'service_inst.py')), '')
try:
    install_from_package(_tmp2, actor='normal_plugin')
    check("C6 install_from_package(normal) 拒绝", False, '未抛异常')
except PluginAdminPermissionError as _e:
    check("C6 install_from_package(normal) 拒绝", 'framework:manage' in str(_e), str(_e))

# ------------------------------ D. 插件更新源 ------------------------------
import core.plugin_updates as PU
_fd, _tmp_cache = tempfile.mkstemp(suffix='.json')
os.close(_fd)
os.remove(_tmp_cache)
PU._cache_file = lambda: _tmp_cache

from http.server import BaseHTTPRequestHandler, HTTPServer


class _FeedH(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({
            'latest_version': '2.0.0', 'published_at': '2026-09-07',
            'download_url': 'https://example.com/market_tool.zip', 'sha256': 'abc',
            'changes': '市场插件更新'}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


_srv = HTTPServer(('127.0.0.1', 0), _FeedH)
_port = _srv.server_address[1]
threading.Thread(target=_srv.serve_forever, daemon=True).start()
_feed_url = f'http://127.0.0.1:{_port}/feed.json'

# 构造带 update_feed 的 catalog 条目（复用已安装插件：直接注册模拟 catalog）
global_var.plugin_catalog.append({'name': 'feed_plugin', 'version': '1.0.0',
                                  'update_feed': _feed_url, 'repo': 'https://github.com/x/feed'})
_r = PU.check_plugin_update('feed_plugin', force=True)
check("D1 feed 拉取与版本比较",
      _r['available'] and _r['latest_version'] == '2.0.0' and _r['current_version'] == '1.0.0',
      f"{_r}")
_r2 = PU.check_plugin_update('feed_plugin')
check("D2 缓存命中不重新拉取", _r2['available'], f"{_r2}")
_r3 = PU.check_plugin_update('rootdemo')
check("D3 未声明 update_feed → 空结果",
      _r3['feed_url'] == '' and not _r3['available'] and not _r3['error'], f"{_r3}")
check("D4 批量仅含声明 feed 的插件",
      [u['name'] for u in PU.check_all_plugin_updates(force=True)] == ['feed_plugin'], '')
_srv.shutdown()

# ------------------------------ E. 加载横幅（framework:core 告警） ------------------------------
import logging

_log_buf = io.StringIO()
_h = logging.StreamHandler(_log_buf)
_h.setFormatter(logging.Formatter('%(message)s'))
logging.getLogger('flask.app').addHandler(_h)
try:
    load_plugins()
finally:
    logging.getLogger('flask.app').removeHandler(_h)
check("E1 framework:core 插件加载横幅（Root 权限）",
      'Root 权限' in _log_buf.getvalue() and 'rootdemo' in _log_buf.getvalue(),
      f"log={_log_buf.getvalue()[:160]}")

# ============ 汇总 ============
n_pass = sum(1 for _, c, _ in results if c)
n_fail = len(results) - n_pass
print(f"\n==== Root 域与市场骨架回归（v4.15）：共 {len(results)} 项，通过 {n_pass}，失败 {n_fail} ====")
sys.exit(1 if n_fail else 0)
