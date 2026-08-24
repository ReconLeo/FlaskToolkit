# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""插件包上传/更新/版本校验端到端回归（test client 模式 + 隔离目录，无需外部服务）

通过 mock global_var.BASE_DIR 到临时目录 + sys.path 指向临时 plugins 包，
完全隔离真实项目（不产生任何项目残留、可重复运行）。

覆盖：正常上传 / 冲突拒绝（描述一致性）/ 已存在提示 / 高版本更新 + 版本刷新 /
低版本拒绝 / require_framework_version 拒绝 / 失败包不落盘。

运行：python test_meta_e2e.py
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

# ---------- 隔离目录：mock BASE_DIR + sys.path ----------
_isolated = tempfile.mkdtemp(prefix='metae2e_')
os.makedirs(os.path.join(_isolated, 'plugins'))
# 提供 plugins 包骨架（base_plugin 复制自真实项目，保证插件可继承）
shutil.copy(os.path.join(REAL_BASE, 'plugins', '__init__.py'),
            os.path.join(_isolated, 'plugins', '__init__.py'))
shutil.copy(os.path.join(REAL_BASE, 'plugins', 'base_plugin.py'),
            os.path.join(_isolated, 'plugins', 'base_plugin.py'))
# 让 import 'plugins.*' 优先从隔离目录解析
sys.path.insert(0, _isolated)
global_var.BASE_DIR = _isolated

import app as appmod
from core.plugin_loader import load_plugins

app = appmod.app
app.config["TESTING"] = True
load_plugins()  # 扫描隔离目录（无插件，游客模式放行）

results = []


def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")


# ---------------- 测试插件构造 ----------------
DEMO_PY = '''
from plugins.base_plugin import BasePlugin

class DemoPackPlugin(BasePlugin):
    name = "demo_pack"
    title = "演示插件"
    version = "1.0.1"
    author = "Test"
    category = "测试"
    description = "上传/更新端到端测试插件"
    permission = "admin"
    dependencies = []

    @property
    def routes(self):
        return []
'''

DEMO_JSON = {
    "name": "demo_pack", "title": "演示插件", "version": "1.0.1",
    "author": "Test", "category": "测试",
    "description": "上传/更新端到端测试插件", "permission": "admin",
    "dependencies": [],
}


def build_zip(py_source, json_obj):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('plugin.json', json.dumps(json_obj, ensure_ascii=False).encode('utf-8'))
        zf.writestr('demo_pack.py', py_source)
    buf.seek(0)
    return buf


def upload(client, buf, filename):
    return client.post('/api/admin/plugins/upload',
                       data={'file': (buf, filename, 'application/zip')},
                       content_type='multipart/form-data')


def main():
    client = app.test_client()

    def plugins_data():
        # 隔离模式下无 auth 插件 → 游客放行，无需 token
        r = client.get('/api/admin/plugins')
        return r.get_json().get('data', [])

    # 1. 上传 demo_pack v1.0.1
    r = upload(client, build_zip(DEMO_PY, DEMO_JSON), 'demo_pack.zip')
    check('上传 v1.0.1 成功', r.status_code == 200 and r.get_json().get('code') == 200,
          f'status={r.status_code} body={r.get_data(as_text=True)[:80]}')

    # 2. catalog version = 1.0.1
    dp = [p for p in plugins_data() if p.get('name') == 'demo_pack']
    check('catalog version=1.0.1', dp and dp[0]['version'] == '1.0.1',
          f"version={dp[0]['version'] if dp else 'N/A'}")

    # 3. 冲突包（version 9.9.9 vs 类 1.0.1）→ 400 拒绝
    conflict = dict(DEMO_JSON)
    conflict['version'] = '9.9.9'
    r = upload(client, build_zip(DEMO_PY, conflict), 'demo_conflict.zip')
    msg = r.get_json().get('message', '') if r.status_code in (200, 400) else ''
    check('冲突包拒绝', r.status_code == 400 and 'version' in msg and '冲突' in msg,
          f'status={r.status_code} msg={msg[:60]}')

    # 4. 正常包已存在 → 400 已存在
    r = upload(client, build_zip(DEMO_PY, DEMO_JSON), 'demo_dup.zip')
    check('已存在提示更新', r.status_code == 400 and '已存在' in r.get_json().get('message', ''),
          f'status={r.status_code}')

    # 5. update v1.0.2（json+py 同步）
    py_v102 = DEMO_PY.replace('version = "1.0.1"', 'version = "1.0.2"')
    js_v102 = dict(DEMO_JSON)
    js_v102['version'] = '1.0.2'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('plugin.json', json.dumps(js_v102, ensure_ascii=False).encode('utf-8'))
        zf.writestr('demo_pack.py', py_v102)
    buf.seek(0)
    r = client.post('/api/admin/plugins/demo_pack/update',
                    data={'file': (buf, 'demo_pack_v102.zip', 'application/zip')},
                    content_type='multipart/form-data')
    check('update v1.0.2 成功', r.status_code == 200, f'status={r.status_code}')

    # 6. catalog version 刷新为 1.0.2
    dp = [p for p in plugins_data() if p.get('name') == 'demo_pack']
    check('version 刷新为 1.0.2', dp and dp[0]['version'] == '1.0.2',
          f"version={dp[0]['version'] if dp else 'N/A'}")

    # 7. 低版本 update → 拒绝
    r = client.post('/api/admin/plugins/demo_pack/update',
                    data={'file': (build_zip(DEMO_PY, DEMO_JSON), 'demo_pack_v101.zip', 'application/zip')},
                    content_type='multipart/form-data')
    check('低版本 update 拒绝', r.status_code == 400 and '版本必须高于' in r.get_json().get('message', ''),
          f'status={r.status_code}')

    # 8. require_framework_version 5.0.0（> 4.2.0）→ 拒绝
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('plugin.json', json.dumps(
            {'name': 'demo_req', 'version': '1.0.0', 'require_framework_version': '5.0.0'},
            ensure_ascii=False).encode('utf-8'))
        zf.writestr('demo_req.py', 'from plugins.base_plugin import BasePlugin\n'
                                  'class DemoReq(BasePlugin):\n'
                                  '    name = "demo_req"\n    version = "1.0.0"\n'
                                  '    require_framework_version = "5.0.0"\n'
                                  '    @property\n    def routes(self):\n        return []\n')
    buf.seek(0)
    r = client.post('/api/admin/plugins/upload',
                    data={'file': (buf, 'demo_req.zip', 'application/zip')},
                    content_type='multipart/form-data')
    msg = r.get_json().get('message', '') if r.status_code in (200, 400) else ''
    check('require_framework_version 拒绝', r.status_code == 400 and '框架最低版本' in msg,
          f'status={r.status_code} msg={msg[:60]}')

    # 9. demo_req 未落盘（parse 拒绝）
    check('demo_req 未落盘',
          not os.path.isfile(os.path.join(global_var.BASE_DIR, 'plugins', 'demo_req.py')),
          f"exists={os.path.isfile(os.path.join(global_var.BASE_DIR, 'plugins', 'demo_req.py'))}")

    # 10. 隔离目录无越界文件（未污染真实项目）
    check('真实项目未被污染',
          not os.path.isfile(os.path.join(REAL_BASE, 'plugins', 'demo_pack.py')),
          f"real_demo_pack_exists={os.path.isfile(os.path.join(REAL_BASE, 'plugins', 'demo_pack.py'))}")

    # 清理隔离目录（受限环境失败时由外部兜底）
    try:
        shutil.rmtree(_isolated, ignore_errors=True)
    except Exception:
        pass

    passed = sum(1 for _, c, _ in results if c)
    print(f"\n==== 插件包元信息端到端 共 {len(results)} 项，通过 {passed}，失败 {len(results) - passed} ====")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == '__main__':
    main()
