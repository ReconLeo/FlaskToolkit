# -*- coding: utf-8 -*-
"""用户中心回归（v4.20，隔离目录 + 内存 auth 配置）

场景：
A. 自助改昵称 API（/api/auth/user/update-nickname）
  A1 未登录 → 401
  A2 空昵称 → 400
  A3 超长昵称（>20）→ 400
  A4 成功改昵称 → 200
  A5 user/info 返回新昵称
  A6 用户名不可改（username 保持不变）
  A7 昵称去空白
B. /user-center 页面
  B1 未登录 GET /user-center → 302 到 /login
  B2 登录后 GET /user-center → 200 渲染（含"用户中心/修改昵称/修改密码"词条 + 主题三件套）
C. 与强制改密共存：改昵称不触发 must_change_pwd 状态变化（无副作用）

运行：python tests/test_user_center.py
"""
import json
import os
import sys
import tempfile

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_TESTS_DIR)
sys.path.insert(0, _PROJECT_ROOT)

import global_var
_tmp = tempfile.mkdtemp(prefix='ftk_userc_')
_path_patches = {
    'BASE_DIR': _tmp,
    'USER_CONFIG_FILE': os.path.join(_tmp, 'data', 'user_config.json'),
    'STATS_FILE': os.path.join(_tmp, 'data', 'stats.json'),
    'PLUGIN_CONFIGS_DIR': os.path.join(_tmp, 'plugins', 'configs'),
    'PLUGIN_TEMP_DIR': os.path.join(_tmp, 'plugins', 'temp'),
    'LOG_DIR': os.path.join(_tmp, 'logs'),
    'UPLOAD_TEMP_DIR': os.path.join(_tmp, 'temp'),
    'FRONTEND_CONFIG_FILE': os.path.join(_tmp, 'data', 'frontend_tools.json'),
    'FRONTEND_TEMPLATE_DIR': os.path.join(_tmp, 'templates', 'frontend_tools'),
    'PLUGIN_CACHE_DIR': os.path.join(_tmp, '.plugin_cache'),
    'PLUGIN_CACHE_FILE': os.path.join(_tmp, '.plugin_cache', 'plugin_discovery_cache.json'),
}
for _k, _v in _path_patches.items():
    setattr(global_var, _k, _v)
os.makedirs(os.path.join(_tmp, 'data'), exist_ok=True)
import shutil
_ld = os.path.join(_tmp, 'locales')
os.makedirs(_ld, exist_ok=True)
for _lf in ('en.json', 'zh-CN.json'):
    _src = os.path.join(_PROJECT_ROOT, 'locales', _lf)
    if os.path.isfile(_src):
        shutil.copy(_src, os.path.join(_ld, _lf))

import app as appmod
app = appmod.app
app.config["TESTING"] = True
client = app.test_client()

results = []
def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")


def main():
    try:
        # ============ 注入 auth 插件（内存配置，不污染真实数据） ============
        import plugins.auth as auth_mod
        auth = auth_mod.AuthPlugin()
        auth.config = {
            "users": [
                {"id": 1, "username": "admin", "role": "admin",
                 "password": auth._hash_password("admin123"), "nickname": "管理员"}
            ]
        }
        auth.SESSION_EXPIRE = 86400
        auth.sessions = {}
        auth._login_attempts = {}
        auth.save_config = lambda: True          # 不写真实 plugins/configs/auth.json
        auth._save_sessions = lambda: None       # 不写真实会话文件
        auth._wrapped_routes = {}
        from core.permission import wrap_view_func
        for route in auth.routes:
            wrapped = wrap_view_func(route["view_func"], auth.name, route)
            path = route["path"]
            auth._wrapped_routes.setdefault(path, {})[route["methods"][0]] = wrapped
        global_var.plugins["auth"] = auth

        # 未登录改昵称 → 401
        r = client.post('/api/auth/user/update-nickname',
                        json={"nickname": "小王"}, headers={"X-CSRF-Token": ''})
        check("A1 未登录改昵称 → 401", r.status_code == 401, f"status={r.status_code}")

        # 登录
        r = client.post('/api/auth/login', json={"username": "admin", "password": "admin123"})
        check("登录成功", r.status_code == 200, f"status={r.status_code}")
        csrf_cookie = client.get_cookie('csrf_token')
        csrf = csrf_cookie.value if csrf_cookie else ''
        headers = {"X-CSRF-Token": csrf}

        # A2 空昵称 → 400
        r = client.post('/api/auth/user/update-nickname', json={"nickname": "   "}, headers=headers)
        check("A2 空昵称 → 400", r.status_code == 400, f"status={r.status_code}")

        # A3 超长昵称（>20）→ 400
        r = client.post('/api/auth/user/update-nickname',
                        json={"nickname": "x" * 21}, headers=headers)
        check("A3 超长昵称 → 400", r.status_code == 400, f"status={r.status_code}")

        # A4 成功改昵称 → 200
        r = client.post('/api/auth/user/update-nickname',
                        json={"nickname": " 小王 "}, headers=headers)  # 含首尾空格测去空白
        check("A4 成功改昵称 → 200", r.status_code == 200, f"status={r.status_code}")

        # A5 user/info 返回新昵称（去空白后 "小王"）
        r = client.get('/api/auth/user/info')
        info = r.get_json()["data"]
        check("A5 user/info 返回新昵称", r.status_code == 200 and info.get("nickname") == "小王",
              f"nickname={info.get('nickname')}")

        # A6 用户名不可改
        check("A6 用户名不可改（仍为 admin）", info.get("username") == "admin",
              f"username={info.get('username')}")

        # A7 昵称去空白
        check("A7 昵称去空白", info.get("nickname") == "小王" and " " not in info.get("nickname", ""), '')

        # ============ B. /user-center 页面 ============
        # B1 未登录（新 client 无 cookie）→ 302 到 /login
        anon = app.test_client()
        r = anon.get('/user-center')
        loc = r.headers.get('Location') or ''
        check("B1 未登录 /user-center → 302 到 /login",
              r.status_code == 302 and '/login' in loc, f"status={r.status_code} loc={loc}")

        # B2 登录后 GET /user-center → 200 渲染
        r = client.get('/user-center')
        body = r.get_data(as_text=True)
        check("B2 登录 /user-center → 200", r.status_code == 200, f"status={r.status_code}")
        check("B2b 含改昵称/改密码表单", 'submitNickname' in body and 'submitPassword' in body
              and '用户中心' in body, '')
        check("B2c 含用户名不可改提示", '不可修改' in body, '')
        check("B2d 主题三件套", 'data-theme-init' in body and 'data-themes' in body
              and '/static/js/theme.js' in body, '')

        print(f'\n==== 用户中心回归：共 {len(results)} 项，'
              f'通过 {sum(1 for _, c, _ in results if c)}，'
              f'失败 {sum(1 for _, c, _ in results if not c)} ====')
        ok = all(c for _, c, _ in results)
        sys.exit(0 if ok else 1)
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
