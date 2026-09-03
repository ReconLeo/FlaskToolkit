# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""管理端 API 单元测试（test client 模式 + 隔离目录，无 auth 插件 → 游客放行，不污染真实项目）

覆盖：
- /api/admin/system/info 字段完整性（framework_version / builtin_plugins / base_dir 等）
- /api/admin/plugins、/api/admin/stats、/api/admin/logs（含非法 level 回退）
- /api/admin/factory-reset scope 校验（空列表 400 / 非法 scope 无副作用 / 非法 JSON 容错）
- 插件包上传：非 zip 400、缺文件 400、超大包 413（P0-1 上传大小限制落地验证）
- core.utils.check_upload_size 单元：超限返回大小 / 未超限 0 / 不可 seek 0

运行：python test_admin_api.py
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
from core.utils import check_upload_size

# ---------- 隔离目录 ----------
_isolated = tempfile.mkdtemp(prefix='ftk_adminapi_')
os.makedirs(os.path.join(_isolated, 'plugins'))
os.makedirs(os.path.join(_isolated, 'temp'))
os.makedirs(os.path.join(_isolated, 'logs'))
shutil.copy(os.path.join(REAL_BASE, 'plugins', '__init__.py'),
            os.path.join(_isolated, 'plugins', '__init__.py'))
shutil.copy(os.path.join(REAL_BASE, 'plugins', 'base_plugin.py'),
            os.path.join(_isolated, 'plugins', 'base_plugin.py'))
sys.path.insert(0, _isolated)

_SAVED = {}
# 关键：FRONTEND_CONFIG_FILE / FRONTEND_TEMPLATE_DIR 必须一并 mock 到隔离目录，
# 否则 factory-reset 的默认 all 会清空真实项目的 frontend_tools（曾因此污染真实项目）
for attr, val in (('BASE_DIR', _isolated), ('UPLOAD_TEMP_DIR', os.path.join(_isolated, 'temp')),
                  ('LOG_DIR', os.path.join(_isolated, 'logs')),
                  ('PLUGIN_CONFIGS_DIR', os.path.join(_isolated, 'plugins', 'configs')),
                  ('FRONTEND_CONFIG_FILE', os.path.join(_isolated, 'frontend_tools.json')),
                  ('FRONTEND_TEMPLATE_DIR', os.path.join(_isolated, 'templates', 'frontend_tools'))):
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

def build_plugin_zip(size_bytes=100):
    """构造插件包 zip（BytesIO）；size_bytes>0 时在包内塞入该大小的填充内容"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_STORED) as zf:
        zf.writestr('plugin.json', json.dumps({
            "name": "big_pack", "version": "1.0.0", "permission": "user",
            "author": "T", "category": "测试", "description": "大小限制测试"
        }, ensure_ascii=False).encode('utf-8'))
        zf.writestr('big_pack.py', '# -*- coding: utf-8 -*-\nfrom plugins.base_plugin import BasePlugin\n')
        if size_bytes > 0:
            zf.writestr('filler.bin', b'x' * size_bytes)
    buf.seek(0)
    return buf


def main():
    client = app.test_client()

    # 1. system/info
    r = client.get('/api/admin/system/info')
    data = r.get_json().get('data', {}) if r.status_code == 200 else {}
    check('system/info 返回 200', r.status_code == 200, f'status={r.status_code}')
    check('system/info framework_version=4.2.2',
          data.get('framework_version') == '4.3.0', f"{data.get('framework_version')}")
    check('system/info builtin_plugins 含 auth/user_manage',
          set(data.get('builtin_plugins', [])) == {'auth', 'user_manage'},
          f"{data.get('builtin_plugins')}")
    check('system/info base_dir=隔离目录',
          data.get('base_dir') == _isolated, f"{data.get('base_dir')}")
    check('system/info python_version 非空', bool(data.get('python_version')), '')
    check('system/info platform 非空', bool(data.get('platform')), '')
    check('system/info host 非空', bool(data.get('host')), '')

    # 2. plugins 列表
    r = client.get('/api/admin/plugins')
    check('plugins 列表 200 + data 为 list',
          r.status_code == 200 and isinstance(r.get_json().get('data'), list),
          f'status={r.status_code}')

    # 3. stats
    r = client.get('/api/admin/stats')
    check('stats 200', r.status_code == 200, f'status={r.status_code}')

    # 4. logs
    r = client.get('/api/admin/logs?level=info')
    check('logs 200（隔离空日志 → data 空列表）',
          r.status_code == 200 and r.get_json().get('data') == [],
          f'status={r.status_code} data={r.get_json().get("data")}')
    r = client.get('/api/admin/logs?level=bogus&lines=abc')
    check('logs 非法 level/lines 容错不 500', r.status_code == 200, f'status={r.status_code}')

    # 5. factory-reset scope 校验
    r = client.post('/api/admin/factory-reset', json={'scope': []})
    check('factory-reset 空 scope 列表 → 400',
          r.status_code == 400, f'status={r.status_code}')
    r = client.post('/api/admin/factory-reset', json={'scope': 'bogus'})
    check('factory-reset 非法 scope → 200（无清理）',
          r.status_code == 200 and r.get_json().get('data', {}).get('cleaned') == [],
          f'status={r.status_code} body={r.get_data(as_text=True)[:80]}')
    r = client.post('/api/admin/factory-reset', data='{bad json',
                    content_type='application/json')
    check('factory-reset 非法 JSON → 200（容错）', r.status_code == 200, f'status={r.status_code}')

    # 6. 上传：缺文件 / 非 zip / 超大包
    r = client.post('/api/admin/plugins/upload', data={})
    check('上传缺文件 → 400', r.status_code == 400, f'status={r.status_code}')
    r = client.post('/api/admin/plugins/upload',
                    data={'file': (io.BytesIO(b'x'), 'bad.txt', 'text/plain')},
                    content_type='multipart/form-data')
    check('上传非 zip → 400', r.status_code == 400, f'status={r.status_code}')

    # 超大包：包内填充 >10MB → 413（P0-1 上传大小限制落地）
    big = build_plugin_zip(size_bytes=11 * 1024 * 1024)
    r = client.post('/api/admin/plugins/upload',
                    data={'file': (big, 'big_pack.zip', 'application/zip')},
                    content_type='multipart/form-data')
    check('上传超大插件包 → 413', r.status_code == 413,
          f'status={r.status_code} body={r.get_data(as_text=True)[:80]}')
    # 未落盘（插件文件不应被创建）
    check('413 后插件未落盘',
          not os.path.exists(os.path.join(_isolated, 'plugins', 'big_pack.py')), '')

    # 7. check_upload_size 单元测试
    under = io.BytesIO(b'x' * 100)
    check('check_upload_size 未超限返回 0',
          check_upload_size(under, 1024) == 0, '')
    over = io.BytesIO(b'x' * 2048)
    check('check_upload_size 超限返回实际大小',
          check_upload_size(over, 1024) == 2048, '')
    # 流不可 seek 时返回 0（不阻断）
    class NoSeek:
        stream = None  # 无 stream 且自身不可 seek
        def seek(self, *a):
            raise OSError('no seek')
        def tell(self):
            return 0
    check('check_upload_size 不可 seek 返回 0',
          check_upload_size(NoSeek(), 10) == 0, '')


if __name__ == '__main__':
    try:
        main()
    finally:
        # 恢复路径常量
        for attr, val in _SAVED.items():
            if val is None:
                try:
                    delattr(global_var, attr)
                except AttributeError:
                    pass
            else:
                setattr(global_var, attr, val)
        try:
            shutil.rmtree(_isolated, ignore_errors=True)
        except Exception:
            pass

    passed = sum(1 for _, c, _ in results if c)
    print(f"\n==== 管理端 API 测试 共 {len(results)} 项，通过 {passed}，失败 {len(results) - passed} ====")
    sys.exit(0 if passed == len(results) else 1)
