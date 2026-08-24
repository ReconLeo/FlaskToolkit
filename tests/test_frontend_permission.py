# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""前端工具访问控制（permission 三层）+ 改权限 API + update 保留 permission 回归
隔离目录（mock 前端配置/模板 + auth 配置到 /tmp）+ test_client + 手动加载 auth，
不污染真实项目（auth 会话文件除外，属运行时数据、已 gitignore）。

为隔离各登录态的 CSRF cookie，使用三个独立 test_client（匿名/管理员/普通用户）。

覆盖：
- auth 未装：任意权限的工具页面放行（可选鉴权）
- auth 已装未登录：public 200 / user 302 login / admin 302 login
- 管理员：user/admin 均 200；普通用户：user 200 / admin 403
- 改权限 API：普通用户 403 / 非法值 400 / 管理员改成功（未登录行为随之变化）/ 不存在工具 404
- 静态资源与页面权限一致（admin 权限下未登录访问静态资源 302）
- update：config 无 permission 字段保留原值，带字段则更新
运行：python tests/test_frontend_permission.py
"""
import io
import json
import os
import shutil
import sys
import tempfile
import zipfile

# ---------- 隔离目录：mock 前端工具 + auth 配置路径 ----------
_isolated = tempfile.mkdtemp(prefix='ftk_ftperm_')
for sub in ('plugins/configs', 'plugins/data', 'templates/frontend_tools/static', 'temp', 'data'):
    os.makedirs(os.path.join(_isolated, sub), exist_ok=True)

import global_var

_SAVED = {}
for _attr, _val in (
        ('BASE_DIR', _isolated),
        ('UPLOAD_TEMP_DIR', os.path.join(_isolated, 'temp')),
        ('FRONTEND_TEMPLATE_DIR', os.path.join(_isolated, 'templates', 'frontend_tools')),
        ('FRONTEND_CONFIG_FILE', os.path.join(_isolated, 'frontend_tools.json')),
        ('STATS_FILE', os.path.join(_isolated, 'data', 'stats.json')),
        ('PLUGIN_CONFIGS_DIR', os.path.join(_isolated, 'plugins', 'configs')),
):
    _SAVED[_attr] = getattr(global_var, _attr, None)
    setattr(global_var, _attr, _val)

import app as appmod
from core.frontend_tools import load_frontend_tools
from core.permission import wrap_view_func

app = appmod.app
app.config["TESTING"] = True

# 模板加载：隔离目录 templates 优先（前端工具页面），真实 templates 兜底（基础页面 404/403 等）
from jinja2 import ChoiceLoader, FileSystemLoader
app.jinja_env.loader = ChoiceLoader([
    FileSystemLoader(os.path.join(_isolated, 'templates')),
    FileSystemLoader(os.path.join(_PROJECT_ROOT, 'templates')),
])

results = []


def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")


def login_user(client, username, password):
    """登录并返回 (token, csrf_header)；test_client 自动维护该 client 的 cookie jar"""
    r = client.post('/api/auth/login', json={'username': username, 'password': password})
    if r.status_code != 200 or r.get_json().get('code') != 200:
        raise SystemExit(f'登录失败 {username}: {r.status_code} {r.get_data(as_text=True)[:120]}')
    token = r.get_json()['data']['token']
    csrf = None
    for _c in r.headers.getlist('Set-Cookie'):
        if _c.strip().startswith('csrf_token='):
            csrf = _c.split(';', 1)[0].split('=', 1)[1]
    return token, {'X-Token': token, 'X-CSRF-Token': csrf}


def add_tool(name, permission, version='1.0.0'):
    """在隔离目录直接注册一个前端工具（html + frontend_tools.json 条目）"""
    os.makedirs(global_var.FRONTEND_TEMPLATE_DIR, exist_ok=True)
    with open(os.path.join(global_var.FRONTEND_TEMPLATE_DIR, f'{name}.html'), 'w', encoding='utf-8') as f:
        f.write(f'<html><body>{name}</body></html>')
    tools = []
    if os.path.exists(global_var.FRONTEND_CONFIG_FILE):
        tools = json.load(open(global_var.FRONTEND_CONFIG_FILE, encoding='utf-8'))
    tools.append({'name': name, 'title': name, 'author': 't', 'description': 'd',
                  'category': '测试', 'version': version, 'permission': permission,
                  'require_framework_version': '', 'enabled': True, 'type': 'frontend'})
    json.dump(tools, open(global_var.FRONTEND_CONFIG_FILE, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)


def build_tool_zip(name, version, permission=None):
    """构造前端工具 zip（permission 可选，None 则 config.json 不含该字段）"""
    cfg = {"name": name, "version": version, "category": "测试", "title": name, "author": "T"}
    if permission is not None:
        cfg['permission'] = permission
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('config.json', json.dumps(cfg, ensure_ascii=False).encode('utf-8'))
        zf.writestr(f'{name}.html', f'<html><body>{name} v{version}</body></html>')
    buf.seek(0)
    return buf


def main():
    try:
        anon = app.test_client()      # 匿名（cookie jar 无登录态）
        admin = app.test_client()     # 管理员
        normal = app.test_client()    # 普通用户

        # ============ A. auth 未装：所有工具放行 ============
        add_tool('tool_public', 'public')
        add_tool('tool_user', 'user')
        add_tool('tool_admin', 'admin')
        load_frontend_tools()
        for name in ('tool_public', 'tool_user', 'tool_admin'):
            r = anon.get(f'/frontend/{name}')
            check(f'A auth未装 {name} 放行', r.status_code == 200, f'status={r.status_code}')

        # ============ 安装 auth（手动加载，等价于 load_plugins 启用分支） ============
        import plugins.auth as auth_mod
        auth = auth_mod.AuthPlugin()
        auth.on_load()  # 隔离 PLUGIN_CONFIGS_DIR：初始化默认 admin/admin123
        for route in auth.routes:
            wrapped = wrap_view_func(route['view_func'], auth.name, route)
            if not hasattr(auth, '_wrapped_routes'):
                auth._wrapped_routes = {}
            path = route['path']
            methods = tuple(route.get('methods', ['GET']))
            auth._wrapped_routes.setdefault(path, {})[methods] = wrapped
        global_var.plugins['auth'] = auth

        # ============ B. auth 已装、未登录 ============
        r = anon.get('/frontend/tool_public', follow_redirects=False)
        check('B 未登录 public 200', r.status_code == 200, f'status={r.status_code}')
        r = anon.get('/frontend/tool_user', follow_redirects=False)
        check('B 未登录 user 302 login', r.status_code == 302 and '/login' in r.headers.get('Location', ''),
              f'status={r.status_code} loc={r.headers.get("Location", "")}')
        r = anon.get('/frontend/tool_admin', follow_redirects=False)
        check('B 未登录 admin 302 login', r.status_code == 302 and '/login' in r.headers.get('Location', ''),
              f'status={r.status_code} loc={r.headers.get("Location", "")}')

        # ============ 管理员 / 普通用户 登录（独立 client，隔离 CSRF cookie） ============
        _at, admin_h = login_user(admin, 'admin', 'admin123')
        auth.create_user('user1', 'pass123', role='user')
        _ut, normal_h = login_user(normal, 'user1', 'pass123')

        # ============ C. 管理员访问 ============
        r = admin.get('/frontend/tool_user')
        check('C 管理员访问 user 200', r.status_code == 200, f'status={r.status_code}')
        r = admin.get('/frontend/tool_admin')
        check('C 管理员访问 admin 200', r.status_code == 200, f'status={r.status_code}')

        # ============ D. 普通用户访问 ============
        r = normal.get('/frontend/tool_user')
        check('D 普通用户访问 user 200', r.status_code == 200, f'status={r.status_code}')
        r = normal.get('/frontend/tool_admin')
        check('D 普通用户访问 admin 403', r.status_code == 403, f'status={r.status_code}')

        # ============ E. 改权限 API ============
        r = normal.post('/api/admin/frontend/tool_public/permission', json={'permission': 'admin'}, headers=normal_h)
        check('E 普通用户改权限 403', r.status_code == 403, f'status={r.status_code} body={r.get_data(as_text=True)[:40]}')
        r = admin.post('/api/admin/frontend/tool_public/permission', json={'permission': 'invalid'}, headers=admin_h)
        check('E 非法权限值 400', r.status_code == 400, f'status={r.status_code}')
        r = admin.post('/api/admin/frontend/tool_public/permission', json={'permission': 'user'}, headers=admin_h)
        check('E 管理员改权限 200', r.status_code == 200, f'status={r.status_code}')
        r = anon.get('/frontend/tool_public', follow_redirects=False)
        check('E 改为 user 后未登录 302', r.status_code == 302 and '/login' in r.headers.get('Location', ''),
              f'status={r.status_code} loc={r.headers.get("Location", "")}')
        admin.post('/api/admin/frontend/tool_public/permission', json={'permission': 'public'}, headers=admin_h)
        r = anon.get('/frontend/tool_public', follow_redirects=False)
        check('E 改回 public 后未登录 200', r.status_code == 200, f'status={r.status_code}')
        r = admin.post('/api/admin/frontend/nonexist_tool/permission', json={'permission': 'public'}, headers=admin_h)
        check('E 不存在工具 404', r.status_code == 404, f'status={r.status_code}')

        # ============ F. 静态资源与页面权限一致 ============
        static_root = os.path.join(global_var.FRONTEND_TEMPLATE_DIR, 'static', 'tool_admin')
        os.makedirs(static_root, exist_ok=True)
        with open(os.path.join(static_root, 'f.txt'), 'w', encoding='utf-8') as f:
            f.write('x')
        r = anon.get('/frontend-static/tool_admin/f.txt', follow_redirects=False)
        check('F 未登录访问 admin 静态 302', r.status_code == 302 and '/login' in r.headers.get('Location', ''),
              f'status={r.status_code}')
        r = admin.get('/frontend-static/tool_admin/f.txt')
        check('F 管理员访问 admin 静态 200', r.status_code == 200, f'status={r.status_code}')
        r = anon.get('/frontend-static/tool_public/f.txt', follow_redirects=False)
        check('F public 工具静态未登录放行（返回 404 而非 302 拦截）', r.status_code != 302, f'status={r.status_code}')

        # ============ G. update 保留 permission ============
        # 上传带 permission=user 的工具
        r = admin.post('/api/admin/frontend/upload',
                       data={'file': (build_tool_zip('upd_tool', '1.0.0', permission='user'),
                                      'upd_tool.zip', 'application/zip')},
                       headers=admin_h, content_type='multipart/form-data')
        check('G 上传 permission=user 工具 200', r.status_code == 200, f'status={r.status_code}')
        r = anon.get('/frontend/upd_tool', follow_redirects=False)
        check('G 上传后未登录 302（user 权限）', r.status_code == 302, f'status={r.status_code}')
        # update 无 permission 字段 → 应保留原 user 权限
        r = admin.post('/api/admin/frontend/upd_tool/update',
                       data={'file': (build_tool_zip('upd_tool', '1.0.1', permission=None),
                                      'upd_tool.zip', 'application/zip')},
                       headers=admin_h, content_type='multipart/form-data')
        check('G 更新(无permission) 200', r.status_code == 200, f'status={r.status_code}')
        r = anon.get('/frontend/upd_tool', follow_redirects=False)
        check('G 更新后仍保留 user 权限 302', r.status_code == 302, f'status={r.status_code}')
        # update 带 permission=public → 权限更新
        r = admin.post('/api/admin/frontend/upd_tool/update',
                       data={'file': (build_tool_zip('upd_tool', '1.0.2', permission='public'),
                                      'upd_tool.zip', 'application/zip')},
                       headers=admin_h, content_type='multipart/form-data')
        check('G 更新(带permission=public) 200', r.status_code == 200, f'status={r.status_code}')
        r = anon.get('/frontend/upd_tool', follow_redirects=False)
        check('G 更新后权限变为 public 200', r.status_code == 200, f'status={r.status_code}')

        print(f'\n==== 前端工具访问控制回归：共 {len(results)} 项，通过 {sum(1 for _, c, _ in results if c)}，'
              f'失败 {sum(1 for _, c, _ in results if not c)} ====')
    finally:
        for _attr, _val in _SAVED.items():
            setattr(global_var, _attr, _val)
        try:
            shutil.rmtree(_isolated, ignore_errors=True)
        except Exception:
            pass

    ok = all(c for _, c, _ in results)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
