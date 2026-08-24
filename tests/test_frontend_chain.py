# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""前端工具 上传/更新/卸载 端到端测试（test client + 隔离目录 + 游客放行，不污染真实项目）

覆盖：
- 上传正常包（config.json + <name>.html + static/）→ 200，文件正确落位
- 页面渲染 /frontend/<name> 与静态资源 /frontend-static/<name>/<path>
- 同名拒绝、非 zip 拒绝、缺 config.json / 缺必填字段拒绝
- 更新：高版本 200、低版本 400；clean_static 更新后旧静态资源 404 / 新静态资源 200
- 卸载：页面 404、静态 404、配置文件移除、目录删除
- 超大包 413（P0-1 上传大小限制落地验证）

运行：python test_frontend_chain.py
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

# ---------- 隔离目录 ----------
_isolated = tempfile.mkdtemp(prefix='ftk_fchain_')
os.makedirs(os.path.join(_isolated, 'plugins'))
os.makedirs(os.path.join(_isolated, 'temp'))
os.makedirs(os.path.join(_isolated, 'templates', 'frontend_tools'))
os.makedirs(os.path.join(_isolated, 'data'))
shutil.copy(os.path.join(REAL_BASE, 'plugins', '__init__.py'),
            os.path.join(_isolated, 'plugins', '__init__.py'))
shutil.copy(os.path.join(REAL_BASE, 'plugins', 'base_plugin.py'),
            os.path.join(_isolated, 'plugins', 'base_plugin.py'))
sys.path.insert(0, _isolated)

_SAVED = {}
for attr, val in (
        ('BASE_DIR', _isolated),
        ('UPLOAD_TEMP_DIR', os.path.join(_isolated, 'temp')),
        ('FRONTEND_TEMPLATE_DIR', os.path.join(_isolated, 'templates', 'frontend_tools')),
        ('FRONTEND_CONFIG_FILE', os.path.join(_isolated, 'frontend_tools.json')),
        ('STATS_FILE', os.path.join(_isolated, 'data', 'stats.json')),
        ('PLUGIN_CONFIGS_DIR', os.path.join(_isolated, 'plugins', 'configs')),
):
    _SAVED[attr] = getattr(global_var, attr, None)
    setattr(global_var, attr, val)

import app as appmod
from core.plugin_loader import load_plugins

app = appmod.app
app.config["TESTING"] = True

# 模板加载：隔离目录 templates 优先（前端工具页面），真实 templates 兜底（基础页面 404/403 等）
from jinja2 import ChoiceLoader, FileSystemLoader
app.jinja_env.loader = ChoiceLoader([
    FileSystemLoader(os.path.join(_isolated, 'templates')),
    FileSystemLoader(os.path.join(REAL_BASE, 'templates')),
])

load_plugins()  # 隔离目录无插件 → 游客放行
global_var.frontend_tools = []  # 清空，避免跨环境残留

results = []

def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

def build_tool(name, version, html='<html><body>demo</body></html>',
               static_files=None, omit=None):
    """构造前端工具包。omit: 可省略的成员（如 'config.json'）；static_files: {'path': content}"""
    omit = omit or []
    static_files = static_files or {}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        if 'config.json' not in omit:
            zf.writestr('config.json', json.dumps({
                "name": name, "version": version, "category": "测试",
                "title": name, "author": "T", "description": "链测"
            }, ensure_ascii=False).encode('utf-8'))
        zf.writestr(f'{name}.html', html)
        for path, content in static_files.items():
            zf.writestr(path, content)
    buf.seek(0)
    return buf


def main():
    client = app.test_client()

    # ---- 上传 v1.0.0（含 static/css/demo.css） ----
    buf = build_tool('demo_tool', '1.0.0', static_files={'static/css/demo.css': 'body{}'})
    r = client.post('/api/admin/frontend/upload',
                    data={'file': (buf, 'demo_tool.zip', 'application/zip')},
                    content_type='multipart/form-data')
    check('上传 v1.0.0 成功', r.status_code == 200 and r.get_json().get('code') == 200,
          f'status={r.status_code}')

    ftl = global_var.FRONTEND_TEMPLATE_DIR
    check('入口 html 落位', os.path.exists(os.path.join(ftl, 'demo_tool.html')), '')
    check('静态 css 落位', os.path.exists(os.path.join(ftl, 'static', 'demo_tool', 'css', 'demo.css')), '')

    r = client.get('/frontend/demo_tool')
    check('页面渲染 200', r.status_code == 200 and 'demo' in r.get_data(as_text=True),
          f'status={r.status_code} body={r.get_data(as_text=True)[:60]}')
    r = client.get('/frontend-static/demo_tool/css/demo.css')
    check('静态资源访问 200', r.status_code == 200 and b'body' in r.data, f'status={r.status_code}')

    # ---- 异常上传拒绝 ----
    r = client.post('/api/admin/frontend/upload',
                    data={'file': (io.BytesIO(b'x'), 'x.txt', 'text/plain')},
                    content_type='multipart/form-data')
    check('非 zip → 400', r.status_code == 400, f'status={r.status_code}')

    buf = build_tool('demo_tool2', '1.0.0', omit=['config.json'])
    r = client.post('/api/admin/frontend/upload',
                    data={'file': (buf, 'demo_tool2.zip', 'application/zip')},
                    content_type='multipart/form-data')
    check('缺 config.json → 400', r.status_code == 400, f'status={r.status_code}')

    # 缺必填字段（category 缺失）
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('config.json', json.dumps({"name": "demo_tool3", "version": "1.0.0"}))
        zf.writestr('demo_tool3.html', '<html></html>')
    buf.seek(0)
    r = client.post('/api/admin/frontend/upload',
                    data={'file': (buf, 'demo_tool3.zip', 'application/zip')},
                    content_type='multipart/form-data')
    check('缺必填字段 → 400', r.status_code == 400, f'status={r.status_code}')

    # 同名拒绝
    buf = build_tool('demo_tool', '1.0.0')
    r = client.post('/api/admin/frontend/upload',
                    data={'file': (buf, 'demo_tool.zip', 'application/zip')},
                    content_type='multipart/form-data')
    check('同名上传 → 400 已存在', r.status_code == 400, f'status={r.status_code}')

    # ---- 更新 v1.0.1（static 改为 js/app.js，旧 css 应被 clean_static 清除） ----
    buf = build_tool('demo_tool', '1.0.1',
                     static_files={'static/js/app.js': 'console.log(1)'})
    r = client.post('/api/admin/frontend/demo_tool/update',
                    data={'file': (buf, 'demo_tool.zip', 'application/zip')},
                    content_type='multipart/form-data')
    check('更新 v1.0.1 成功', r.status_code == 200 and r.get_json().get('code') == 200,
          f'status={r.status_code} body={r.get_data(as_text=True)[:80]}')

    cfg = json.load(open(global_var.FRONTEND_CONFIG_FILE, encoding='utf-8'))
    cur = next(t for t in cfg if t['name'] == 'demo_tool')
    check('更新后版本为 1.0.1', cur['version'] == '1.0.1', f"{cur['version']}")

    r = client.get('/frontend-static/demo_tool/js/app.js')
    check('更新后新静态资源 200', r.status_code == 200 and b'console.log' in r.data,
          f'status={r.status_code}')
    r = client.get('/frontend-static/demo_tool/css/demo.css')
    check('更新后旧静态资源 404（clean_static）', r.status_code == 404, f'status={r.status_code}')

    # 低版本更新拒绝
    buf = build_tool('demo_tool', '1.0.0')
    r = client.post('/api/admin/frontend/demo_tool/update',
                    data={'file': (buf, 'demo_tool.zip', 'application/zip')},
                    content_type='multipart/form-data')
    check('低版本更新 → 400', r.status_code == 400, f'status={r.status_code}')

    # 更新后页面仍可访问
    r = client.get('/frontend/demo_tool')
    check('更新后页面 200', r.status_code == 200, f'status={r.status_code}')

    # ---- 卸载 ----
    r = client.post('/api/admin/frontend/demo_tool/uninstall')
    check('卸载成功', r.status_code == 200 and r.get_json().get('code') == 200,
          f'status={r.status_code}')
    check('卸载后 html 删除', not os.path.exists(os.path.join(ftl, 'demo_tool.html')), '')
    check('卸载后 static 目录删除',
          not os.path.exists(os.path.join(ftl, 'static', 'demo_tool')), '')
    cfg = json.load(open(global_var.FRONTEND_CONFIG_FILE, encoding='utf-8'))
    check('卸载后配置移除', all(t['name'] != 'demo_tool' for t in cfg), f'cfg={cfg}')
    r = client.get('/frontend/demo_tool')
    check('卸载后页面 404', r.status_code == 404, f'status={r.status_code}')
    r = client.get('/frontend-static/demo_tool/js/app.js')
    check('卸载后静态 404', r.status_code == 404, f'status={r.status_code}')

    # ---- 超大工具包 → 413（P0-1） ----
    big = io.BytesIO()
    with zipfile.ZipFile(big, 'w', zipfile.ZIP_STORED) as zf:
        zf.writestr('config.json', json.dumps(
            {"name": "big_tool", "version": "1.0.0", "category": "测试"}))
        zf.writestr('big_tool.html', '<html></html>')
        zf.writestr('filler.bin', b'x' * (11 * 1024 * 1024))
    big.seek(0)
    r = client.post('/api/admin/frontend/upload',
                    data={'file': (big, 'big_tool.zip', 'application/zip')},
                    content_type='multipart/form-data')
    check('超大工具包 → 413', r.status_code == 413,
          f'status={r.status_code} body={r.get_data(as_text=True)[:80]}')
    check('413 后工具未落位', not os.path.exists(os.path.join(ftl, 'big_tool.html')), '')


if __name__ == '__main__':
    try:
        main()
    finally:
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
    print(f"\n==== 前端工具链路测试 共 {len(results)} 项，通过 {passed}，失败 {len(results) - passed} ====")
    sys.exit(0 if passed == len(results) else 1)
