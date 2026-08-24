# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""前端工具 上传/更新/卸载 全链路验证（含 static/ 静态资源）"""
import requests
import json
import os

BASE = 'http://127.0.0.1:5000'
s = requests.Session()

def check(name, cond, detail=''):
    print(('PASS' if cond else 'FAIL'), '-', name, detail if not cond else '')

# 登录
r = s.post(BASE + '/api/auth/login', json={'username': 'admin', 'password': 'admin123'})
print('登录:', r.status_code, r.json().get('code'))
csrf = s.cookies.get('csrf_token')
print('csrf_token:', bool(csrf))

def post_upload(zip_path):
    with open(zip_path, 'rb') as f:
        return s.post(BASE + '/api/admin/frontend/upload',
                      files={'file': (os.path.basename(zip_path), f, 'application/zip')},
                      headers={'X-CSRF-Token': csrf})

def post_update(tool, zip_path):
    with open(zip_path, 'rb') as f:
        return s.post(BASE + f'/api/admin/frontend/{tool}/update',
                      files={'file': (os.path.basename(zip_path), f, 'application/zip')},
                      headers={'X-CSRF-Token': csrf})

def post_uninstall(tool):
    return s.post(BASE + f'/api/admin/frontend/{tool}/uninstall',
                  headers={'X-CSRF-Token': csrf})

temp = _PROJECT_ROOT + '/temp'
v1 = os.path.join(temp, 'demo_tool_v1.0.0.zip')
v2 = os.path.join(temp, 'demo_tool_v1.0.1.zip')

# ============ 链路 1：上传 v1.0.0 ============
print('\n===== 链路1：上传 v1.0.0 =====')
r = post_upload(v1)
print('上传响应:', r.status_code, r.text[:120])
check('上传返回200', r.status_code == 200)

pg = s.get(BASE + '/frontend/demo_tool')
check('页面200', pg.status_code == 200)
check('页面含v1.0.0', '1.0.0' in pg.text)

css = s.get(BASE + '/frontend-static/demo_tool/css/style.css')
check('static css 200', css.status_code == 200, f'实际{css.status_code}')
js = s.get(BASE + '/frontend-static/demo_tool/js/app.js')
check('static js 200', js.status_code == 200, f'实际{js.status_code}')
oldjs = s.get(BASE + '/frontend-static/demo_tool/js/old.js')
check('v1 旧文件 old.js 200', oldjs.status_code == 200, f'实际{oldjs.status_code}')

cfg = json.load(open(_PROJECT_ROOT + '/frontend_tools.json', encoding='utf-8'))
check('配置含 demo_tool', any(t['name'] == 'demo_tool' and t['version'] == '1.0.0' for t in cfg))

# ============ 链路 2：更新 v1.0.1 ============
print('\n===== 链路2：更新 v1.0.1 =====')
r = post_update('demo_tool', v2)
print('更新响应:', r.status_code, r.text[:150])
check('更新返回200', r.status_code == 200)

pg = s.get(BASE + '/frontend/demo_tool')
check('页面含v1.0.1', '1.0.1' in pg.text)
check('页面含 v2-badge', 'v2-badge' in pg.text)
check('页面不再含 v1.0.0 版本标记', '>1.0.0<' not in pg.text)

css2 = s.get(BASE + '/frontend-static/demo_tool/css/style.css')
check('更新后 css 200', css2.status_code == 200)
check('更新后 css 含 v2-badge 样式', '.v2-badge' in css2.text)

oldjs2 = s.get(BASE + '/frontend-static/demo_tool/js/old.js')
check('更新后旧文件 old.js 404（已清理）', oldjs2.status_code == 404, f'实际{oldjs2.status_code}')

cfg = json.load(open(_PROJECT_ROOT + '/frontend_tools.json', encoding='utf-8'))
demo = next((t for t in cfg if t['name'] == 'demo_tool'), None)
check('配置版本更新为 1.0.1', demo and demo['version'] == '1.0.1')

# ============ 链路 3：卸载 ============
print('\n===== 链路3：卸载 =====')
r = post_uninstall('demo_tool')
print('卸载响应:', r.status_code, r.text[:150])
check('卸载返回200', r.status_code == 200)

pg = s.get(BASE + '/frontend/demo_tool')
check('卸载后页面404', pg.status_code == 404, f'实际{pg.status_code}')
css3 = s.get(BASE + '/frontend-static/demo_tool/css/style.css')
check('卸载后静态资源404', css3.status_code == 404, f'实际{css3.status_code}')

html_exist = os.path.exists(_PROJECT_ROOT + '/templates/frontend_tools/demo_tool.html')
static_dir_exist = os.path.isdir(_PROJECT_ROOT + '/templates/frontend_tools/static/demo_tool')
check('html 文件已删除', not html_exist)
check('static 目录已删除', not static_dir_exist)

cfg = json.load(open(_PROJECT_ROOT + '/frontend_tools.json', encoding='utf-8'))
check('配置已移除 demo_tool', not any(t['name'] == 'demo_tool' for t in cfg))
print('\n配置剩余工具:', [t['name'] for t in cfg])
print('\n===== 全链路验证完成 =====')
