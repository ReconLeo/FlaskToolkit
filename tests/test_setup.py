# -*- coding: utf-8 -*-
"""首次运行向导 + 强制改密回归（v4.10 M4，隔离目录）

场景：
A. 首次运行向导
  A1 未初始化 GET / → 302 跳转 /setup
  A2 GET /setup → 200（渲染向导页，含框架版本号）
  A3 POST /setup（lang=zh-CN）→ 302 /；data/.setup_done 标记已写入
  A4 data/user_config.json 写入 LANGUAGE=zh-CN
  A5 初始化完成后 GET / → 200（首页放行）
  A6 已初始化 GET /setup → 302 /（不再展示向导）
  A7 重复 POST /setup（lang=en）→ 幂等写标记 + 语言更新

B. 强制改密（auth 场景，内存配置隔离）
  B1 默认密码 admin/admin123 登录 → data.must_change_pwd=True
  B2 错误旧密码改密 → 400
  B3 新密码过短 → 400
  B4 正确改密 → 200
  B5 改密后重新登录 → data.must_change_pwd=False
  B6 改密后旧密码登录失败 → 401
  B7 改密后新密码可正常访问受保护接口（会话可用）

运行：python tests/test_setup.py
"""
import json
import os
import sys
import tempfile

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_TESTS_DIR)
sys.path.insert(0, _PROJECT_ROOT)

# ---------- 隔离环境：patch global_var 路径常量到临时目录 ----------
import global_var
_tmp = tempfile.mkdtemp(prefix='ftk_setup_')
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

import app as appmod
app = appmod.app
app.config["TESTING"] = True
client = app.test_client()

results = []

def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

_SETUP_DONE = os.path.join(_tmp, 'data', '.setup_done')
_USER_CFG = os.path.join(_tmp, 'data', 'user_config.json')


def main():
    # ============ A. 首次运行向导 ============
    try:
        r = client.get('/')
        check("A1 未初始化 GET / → 302 /setup",
              r.status_code == 302 and '/setup' in (r.headers.get('Location') or ''),
              f"status={r.status_code} loc={r.headers.get('Location')}")

        r = client.get('/setup')
        body = r.get_data(as_text=True)
        check("A2 GET /setup → 200", r.status_code == 200, f"status={r.status_code}")
        check("A3 向导页含框架版本号", global_var.FRAMEWORK_VERSION in body, '')

        # POST /setup 完成初始化（选择简体中文）
        r = client.post('/setup', data={'lang': 'zh-CN'})
        check("A4 POST /setup → 302 /",
              r.status_code == 302 and (r.headers.get('Location') or '').endswith('/'),
              f"status={r.status_code} loc={r.headers.get('Location')}")
        check("A5 data/.setup_done 标记已写入", os.path.isfile(_SETUP_DONE), '')
        check("A6 user_config LANGUAGE=zh-CN",
              os.path.isfile(_USER_CFG) and json.load(open(_USER_CFG, encoding='utf-8')).get('LANGUAGE') == 'zh-CN',
              '')

        r = client.get('/')
        check("A7 初始化后 GET / → 200", r.status_code == 200, f"status={r.status_code}")

        r = client.get('/setup')
        check("A8 已初始化 GET /setup → 302 /",
              r.status_code == 302 and (r.headers.get('Location') or '').endswith('/'),
              f"status={r.status_code} loc={r.headers.get('Location')}")

        # 重复提交幂等 + 语言切换
        r = client.post('/setup', data={'lang': 'en'})
        check("A9 重复 POST /setup → 302 /",
              r.status_code == 302 and (r.headers.get('Location') or '').endswith('/'),
              f"status={r.status_code}")
        check("A10 语言更新为 en",
              json.load(open(_USER_CFG, encoding='utf-8')).get('LANGUAGE') == 'en', '')

        # ============ B. 强制改密（注入 auth，内存配置避免污染真实数据） ============
        from core.permission import wrap_view_func
        import plugins.auth as auth_mod
        auth = auth_mod.AuthPlugin()
        auth.config = {
            "SESSION_EXPIRE": 86400,
            "users": [{
                "id": 1,
                "username": "admin",
                "password": auth._hash_password("admin123"),
                "nickname": "管理员",
                "role": "admin",
            }],
        }
        auth.SESSION_EXPIRE = 86400
        auth.sessions = {}
        auth._login_attempts = {}
        auth.save_config = lambda: True          # 不写真实 plugins/configs/auth.json
        auth._save_sessions = lambda: None       # 不写真实会话文件
        auth._wrapped_routes = {}
        for route in auth.routes:
            wrapped = wrap_view_func(route["view_func"], auth.name, route)
            path = route["path"]
            methods = tuple(route.get("methods", ["GET"]))
            auth._wrapped_routes.setdefault(path, {})[methods] = wrapped
        global_var.plugins["auth"] = auth

        # B1 默认密码登录 → 强制改密标记
        r = client.post('/api/auth/login', json={"username": "admin", "password": "admin123"})
        b1 = r.get_json()["data"]
        check("B1 默认密码登录 must_change_pwd=True", b1.get("must_change_pwd") is True,
              f"must={b1.get('must_change_pwd')}")
        csrf_cookie = client.get_cookie('csrf_token')
        csrf = csrf_cookie.value if csrf_cookie else ''

        # B2 错误旧密码 → 400
        r = client.post('/api/auth/change-password',
                        json={"old_password": "wrong", "new_password": "newpass1"},
                        headers={"X-CSRF-Token": csrf})
        check("B2 错误旧密码 → 400", r.status_code == 400, f"status={r.status_code}")

        # B3 新密码过短 → 400
        r = client.post('/api/auth/change-password',
                        json={"old_password": "admin123", "new_password": "123"},
                        headers={"X-CSRF-Token": csrf})
        check("B3 新密码过短 → 400", r.status_code == 400, f"status={r.status_code}")

        # B4 正确改密 → 200
        r = client.post('/api/auth/change-password',
                        json={"old_password": "admin123", "new_password": "newpass1"},
                        headers={"X-CSRF-Token": csrf})
        check("B4 正确改密 → 200", r.status_code == 200, f"status={r.status_code}")

        # B5 改密后重新登录 → 不再强制
        r = client.post('/api/auth/login', json={"username": "admin", "password": "newpass1"})
        b5 = r.get_json()["data"]
        check("B5 改密后登录 must_change_pwd=False", b5.get("must_change_pwd") is False,
              f"must={b5.get('must_change_pwd')}")

        # B6 旧密码登录失败 → 401
        r = client.post('/api/auth/login', json={"username": "admin", "password": "admin123"})
        check("B6 旧密码登录失败 → 401", r.status_code == 401, f"status={r.status_code}")

        # B7 新密码会话可访问受保护接口（user/info 需登录）
        r = client.get('/api/auth/user/info')
        check("B7 新密码会话访问受保护接口 200", r.status_code == 200, f"status={r.status_code}")

        print(f'\n==== 首次运行向导 + 强制改密（v4.10 M4）：共 {len(results)} 项，'
              f'通过 {sum(1 for _, c, _ in results if c)}，'
              f'失败 {sum(1 for _, c, _ in results if not c)} ====')
    finally:
        global_var.plugins.pop('auth', None)

    ok = all(c for _, c, _ in results)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
