# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""前端工具链路验证：真实项目(5000, 模板即时生效) + 副本(5011, 完整含卸载删除)"""
import requests
import json
import os

ZIP_V1 = _PROJECT_ROOT + '/temp/demo_tool_v1.0.0.zip'
ZIP_V2 = _PROJECT_ROOT + '/temp/demo_tool_v1.0.1.zip'

def check(name, cond, detail=''):
    print(('PASS' if cond else 'FAIL'), '-', name, ('' if cond else detail))

def make_client(base):
    s = requests.Session()
    r = s.post(base + '/api/auth/login', json={'username': 'admin', 'password': 'admin123'})
    csrf = s.cookies.get('csrf_token')
    return s, csrf

def upload(s, csrf, base, zip_path):
    with open(zip_path, 'rb') as f:
        return s.post(base + '/api/admin/frontend/upload',
                      files={'file': (os.path.basename(zip_path), f, 'application/zip')},
                      headers={'X-CSRF-Token': csrf})

def update(s, csrf, base, tool, zip_path):
    with open(zip_path, 'rb') as f:
        return s.post(base + f'/api/admin/frontend/{tool}/update',
                      files={'file': (os.path.basename(zip_path), f, 'application/zip')},
                      headers={'X-CSRF-Token': csrf})

def uninstall(s, csrf, base, tool):
    return s.post(base + f'/api/admin/frontend/{tool}/uninstall',
                  headers={'X-CSRF-Token': csrf})

# ============ A. 真实项目 5000：上传 + 更新（模板即时生效） ============
print('\n########## A. 真实项目 (5000) ##########')
s, csrf = make_client('http://127.0.0.1:5000')
r = upload(s, csrf, 'http://127.0.0.1:5000', ZIP_V1)
check('A 上传200', r.status_code == 200, r.text[:120])
pg = s.get('http://127.0.0.1:5000/frontend/demo_tool')
check('A 页面含v1.0.0', '1.0.0' in pg.text)

r = update(s, csrf, 'http://127.0.0.1:5000', 'demo_tool', ZIP_V2)
check('A 更新200', r.status_code == 200, r.text[:120])
pg = s.get('http://127.0.0.1:5000/frontend/demo_tool')
check('A 页面即时显示v1.0.1(模板自动重载)', '1.0.1' in pg.text, pg.text[:80])
check('A 页面含 v2-badge', 'v2-badge' in pg.text)

# ============ B. 副本 5011：完整链路（含卸载删除） ============
print('\n########## B. 副本 (5011, /tmp 无删除限制) ##########')
s2, csrf2 = make_client('http://127.0.0.1:5011')

# 上传
r = upload(s2, csrf2, 'http://127.0.0.1:5011', ZIP_V1)
check('B 上传200', r.status_code == 200, r.text[:120])
pg = s2.get('http://127.0.0.1:5011/frontend/demo_tool')
check('B 页面含v1.0.0', '1.0.0' in pg.text)
css = s2.get('http://127.0.0.1:5011/frontend-static/demo_tool/css/style.css')
check('B static css 200', css.status_code == 200, f'实际{css.status_code}')
oldjs = s2.get('http://127.0.0.1:5011/frontend-static/demo_tool/js/old.js')
check('B v1 old.js 200', oldjs.status_code == 200, f'实际{oldjs.status_code}')

# 更新
r = update(s2, csrf2, 'http://127.0.0.1:5011', 'demo_tool', ZIP_V2)
check('B 更新200', r.status_code == 200, r.text[:120])
pg = s2.get('http://127.0.0.1:5011/frontend/demo_tool')
check('B 页面含v1.0.1', '1.0.1' in pg.text)
check('B 页面含 v2-badge', 'v2-badge' in pg.text)
oldjs2 = s2.get('http://127.0.0.1:5011/frontend-static/demo_tool/js/old.js')
check('B 更新后 old.js 404（clean_static 生效）', oldjs2.status_code == 404, f'实际{oldjs2.status_code}')
css2 = s2.get('http://127.0.0.1:5011/frontend-static/demo_tool/css/style.css')
check('B 更新后 css 含 v2-badge', '.v2-badge' in css2.text)

# 卸载
r = uninstall(s2, csrf2, 'http://127.0.0.1:5011', 'demo_tool')
check('B 卸载200', r.status_code == 200, r.text[:120])
pg = s2.get('http://127.0.0.1:5011/frontend/demo_tool')
check('B 卸载后页面404', pg.status_code == 404, f'实际{pg.status_code}')
css3 = s2.get('http://127.0.0.1:5011/frontend-static/demo_tool/css/style.css')
check('B 卸载后静态404', css3.status_code == 404, f'实际{css3.status_code}')

html_exist = os.path.exists('/tmp/ftk_verify/templates/frontend_tools/demo_tool.html')
static_exist = os.path.isdir('/tmp/ftk_verify/templates/frontend_tools/static/demo_tool')
check('B html 文件已删除', not html_exist)
check('B static 目录已删除', not static_exist)

cfg = json.load(open('/tmp/ftk_verify/frontend_tools.json', encoding='utf-8'))
check('B 配置已移除 demo_tool', not any(t['name'] == 'demo_tool' for t in cfg))
print('B 副本剩余工具:', [t['name'] for t in cfg])
print('\n===== 验证完成 =====')
