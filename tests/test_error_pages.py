# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""统一错误码页面渲染测试（test client + 隔离目录，不污染真实项目）

覆盖六个统一错误码页面（400/401/403/404/405/500）：
- 环境A（无 auth 插件，游客放行）：真实触发 404 / 405 页面；400/500 模板渲染断言
- 环境B（带 auth 插件）：未登录访问管理 API → 401 JSON；未登录访问管理页 → 302 登录；
  admin 登录后管理页 200；普通用户访问管理页 → 403 页面；401/403 模板渲染断言

运行：python test_error_pages.py
"""
import json
import os
import shutil
import sys
import tempfile

REAL_BASE = _PROJECT_ROOT
sys.path.insert(0, REAL_BASE)

import global_var

results = []

def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

def render(app, template, **ctx):
    """在请求上下文中渲染模板（不触发 errorhandler，直接验证模板可渲染），返回 HTML 字符串"""
    with app.test_request_context():
        from flask import render_template
        return render_template(template, **ctx)


def build_env(with_auth=False):
    """构建隔离环境：mock global_var 路径常量 + 复制 plugins 骨架（可选 auth）。返回 (root, saved)"""
    root = tempfile.mkdtemp(prefix='ftk_errpage_')
    os.makedirs(os.path.join(root, 'plugins'))
    os.makedirs(os.path.join(root, 'temp'))
    for fn in ('__init__.py', 'base_plugin.py'):
        shutil.copy(os.path.join(REAL_BASE, 'plugins', fn),
                    os.path.join(root, 'plugins', fn))
    if with_auth:
        shutil.copy(os.path.join(REAL_BASE, 'plugins', 'auth.py'),
                    os.path.join(root, 'plugins', 'auth.py'))
        os.makedirs(os.path.join(root, 'plugins', 'configs'))
        os.makedirs(os.path.join(root, 'plugins', 'data'))
        os.makedirs(os.path.join(root, 'plugins', 'data', 'auth'))
        with open(os.path.join(root, 'plugins', 'configs', 'auth.json'), 'w', encoding='utf-8') as f:
            json.dump({"SESSION_EXPIRE": 86400, "users": []}, f, ensure_ascii=False)
        with open(os.path.join(root, 'plugins', 'data', 'auth', 'sessions.json'), 'w', encoding='utf-8') as f:
            json.dump({}, f)

    sys.path.insert(0, root)  # 让 import 'plugins.*' 从本隔离目录解析
    saved = {}
    for attr, val in (('BASE_DIR', root), ('UPLOAD_TEMP_DIR', os.path.join(root, 'temp')),
                      ('STATS_FILE', os.path.join(root, 'data', 'stats.json'))):
        saved[attr] = getattr(global_var, attr, None)
        setattr(global_var, attr, val)
    return root, saved


def restore_env(saved, root):
    for attr, val in saved.items():
        if val is None:
            try:
                delattr(global_var, attr)
            except AttributeError:
                pass
        else:
            setattr(global_var, attr, val)
    try:
        shutil.rmtree(root, ignore_errors=True)
    except Exception:
        pass


def test_env_a():
    """无 auth：404 / 405 真实触发 + 400/500 模板渲染"""
    root, saved = build_env(with_auth=False)
    try:
        import app as appmod
        from core.plugin_loader import load_plugins
        app = appmod.app
        app.config["TESTING"] = True
        from jinja2 import ChoiceLoader, FileSystemLoader
        app.jinja_env.loader = ChoiceLoader([
            FileSystemLoader(os.path.join(root, 'templates')),
            FileSystemLoader(os.path.join(REAL_BASE, 'templates')),
        ])
        load_plugins()  # 无插件 → 游客放行
        client = app.test_client()

        r = client.get('/no-such-page-xyz')
        check('A: 404 页面真实触发', r.status_code == 404 and '404' in r.get_data(as_text=True),
              f'status={r.status_code}')

        # 注：/api/admin/* 会被插件通配路由 /api/<plugin>/<path> 抢占（GET 返回 404 而非 405），
        # 故 405 用 POST-only 的 /api/plugins 触发（不被通配覆盖）
        r = client.post('/api/plugins')
        check('A: 405 页面真实触发', r.status_code == 405 and '405' in r.get_data(as_text=True),
              f'status={r.status_code} body={r.get_data(as_text=True)[:60]}')

        html = render(app, '400.html', message='x')
        check('A: 400 模板渲染', isinstance(html, str) and '400' in html, '')

        html = render(app, '500.html', message='x')
        check('A: 500 模板渲染', isinstance(html, str) and '500' in html, '')
    finally:
        restore_env(saved, root)


def test_env_b():
    """带 auth：401/403 场景"""
    root, saved = build_env(with_auth=True)
    try:
        import app as appmod
        from core.plugin_loader import load_plugins
        app = appmod.app
        app.config["TESTING"] = True
        from jinja2 import ChoiceLoader, FileSystemLoader
        app.jinja_env.loader = ChoiceLoader([
            FileSystemLoader(os.path.join(root, 'templates')),
            FileSystemLoader(os.path.join(REAL_BASE, 'templates')),
        ])
        load_plugins()  # auth 自动创建 admin/admin123
        client = app.test_client()

        # 未登录访问管理 API → 401 JSON
        r = client.get('/api/admin/plugins')
        body = r.get_json() or {}
        check('B: 未登录管理 API → 401 JSON', r.status_code == 401 and body.get('code') == 401,
              f'status={r.status_code}')

        # 未登录访问管理页 → 302 登录
        r = client.get('/admin/dashboard')
        check('B: 未登录管理页 → 302 登录', r.status_code == 302 and '/login' in r.headers.get('Location', ''),
              f'status={r.status_code} loc={r.headers.get("Location")}')

        # admin 登录 → 管理页 200（独立 client，cookie 隔离）
        client_a = app.test_client()
        r = client_a.post('/api/auth/login', json={'username': 'admin', 'password': 'admin123'})
        check('B: admin 登录成功', r.status_code == 200 and r.get_json().get('code') == 200,
              f'status={r.status_code} body={r.get_data(as_text=True)[:60]}')
        r = client_a.get('/admin/dashboard')
        check('B: admin 访问管理页 200', r.status_code == 200, f'status={r.status_code}')

        # 普通用户：直接创建，独立 client 登录
        global_var.plugins['auth'].create_user('normal', 'pass123', nickname='普通用户', role='user')
        client_b = app.test_client()
        r = client_b.post('/api/auth/login', json={'username': 'normal', 'password': 'pass123'})
        check('B: 普通用户登录成功', r.status_code == 200 and r.get_json().get('code') == 200,
              f'status={r.status_code}')
        r = client_b.get('/admin/dashboard')
        body = r.get_data(as_text=True)
        check('B: 普通用户访问管理页 → 403 页面', r.status_code == 403 and '403' in body,
              f'status={r.status_code} body={body[:60]}')

        # 401/403 模板渲染断言
        html = render(app, '401.html', message='x')
        check('B: 401 模板渲染', isinstance(html, str) and '401' in html, '')
        html = render(app, '403.html', message='x')
        check('B: 403 模板渲染', isinstance(html, str) and '403' in html, '')
    finally:
        restore_env(saved, root)


if __name__ == '__main__':
    test_env_a()
    test_env_b()

    passed = sum(1 for _, c, _ in results if c)
    print(f"\n==== 错误码页面渲染测试 共 {len(results)} 项，通过 {passed}，失败 {len(results) - passed} ====")
    sys.exit(0 if passed == len(results) else 1)
