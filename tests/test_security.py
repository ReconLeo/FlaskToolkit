# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""系统安全回归（v4.3.0 安全强化）

场景：
A. 安全响应头：5 头注入（X-Content-Type-Options/X-Frame-Options/CSP/Referrer-Policy/Permissions-Policy）+ 移除 Server/X-Powered-By
B. 会话 Cookie 加固：token HttpOnly + SameSite=Lax；SECURE 联动（False 无 Secure / True 有 Secure）
C. 会话空闲超时：last_active_at 超时即失效；未超时刷新 last_active_at
D. 登录失败锁定 ip_username（默认）：连续 LOGIN_MAX_ATTEMPTS 次失败后锁定，期间返回通用 429（不泄露锁定细节）；
   换 IP 不受影响（IP+用户名双维度）
E. 登录失败锁定 username：换 IP 仍锁定（仅用户名维度）
F. 登录失败锁定 off：禁用锁定，连续失败不 429
G. 登录成功重置失败计数

运行：python tests/test_security.py
"""
import os
import sys
import time
import json
import shutil
import tempfile

sys.path.insert(0, _PROJECT_ROOT)

import global_var
import app as appmod
from core.permission import wrap_page_func, wrap_view_func

app = appmod.app
app.config["TESTING"] = True

results = []

def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

# ============ 测试夹具：安装 auth 插件 ============
import plugins.auth as auth_mod
auth = auth_mod.AuthPlugin()
auth.on_load()

# 备份将被测试写入的配置文件，测试结束后恢复
_cfg_path = os.path.join(_PROJECT_ROOT, 'plugins', 'auth', 'configs', 'auth.json')
_session_path = os.path.join(_PROJECT_ROOT, 'plugins', 'auth', 'data', 'sessions.json')
_bak_dir = os.path.join(tempfile.gettempdir(), 'flasktoolkit_test_security_bak')
os.makedirs(_bak_dir, exist_ok=True)
for src, name in ((_cfg_path, 'auth.json'), (_session_path, 'sessions.json')):
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(_bak_dir, name))
    else:
        bak = os.path.join(_bak_dir, name)
        if os.path.exists(bak):
            os.remove(bak)

def restore_fixtures():
    for src, name in ((_cfg_path, 'auth.json'), (_session_path, 'sessions.json')):
        bak = os.path.join(_bak_dir, name)
        if os.path.exists(bak):
            shutil.copy2(bak, src)
        elif os.path.exists(src):
            os.remove(src)

# 手动注册路由包装（等价 load_plugins 启用分支）
from plugins.base_plugin import permission  # noqa
for route in auth.routes:
    wrapped = wrap_view_func(route["view_func"], auth.name, route)
    if not hasattr(auth, "_wrapped_routes"):
        auth._wrapped_routes = {}
    path = route["path"]
    methods = tuple(route.get("methods", ["GET"]))
    if path not in auth._wrapped_routes:
        auth._wrapped_routes[path] = {}
    auth._wrapped_routes[path][methods] = wrapped
from global_var import plugins
plugins["auth"] = auth

# 保存 global_var 安全配置原值
_saved_cfg = {k: getattr(global_var, k) for k in (
    'SECURITY_HEADERS', 'SESSION_COOKIE_SECURE', 'LOGIN_MAX_ATTEMPTS',
    'LOGIN_LOCK_SECONDS', 'LOGIN_LOCK_MODE', 'SESSION_IDLE_TIMEOUT')}

def restore_global_var():
    for k, v in _saved_cfg.items():
        setattr(global_var, k, v)

client = app.test_client()

def do_login(c, username="admin", password="admin123", ip=None):
    kwargs = {}
    if ip:
        kwargs['environ_base'] = {'REMOTE_ADDR': ip}
    return c.post("/api/auth/login", json={"username": username, "password": password}, **kwargs)

def main():
    try:
        # ============ A：安全响应头 ============
        global_var.SECURITY_HEADERS = True
        r = client.get("/")
        headers = r.headers
        check("A1 X-Content-Type-Options=nosniff",
              headers.get('X-Content-Type-Options') == 'nosniff',
              f"val={headers.get('X-Content-Type-Options')}")
        check("A2 X-Frame-Options=DENY",
              headers.get('X-Frame-Options') == 'DENY',
              f"val={headers.get('X-Frame-Options')}")
        check("A3 Content-Security-Policy 注入",
              'default-src' in (headers.get('Content-Security-Policy') or ''),
              f"val={headers.get('Content-Security-Policy')}")
        check("A4 Referrer-Policy=no-referrer",
              headers.get('Referrer-Policy') == 'no-referrer',
              f"val={headers.get('Referrer-Policy')}")
        check("A5 Permissions-Policy 注入",
              'geolocation' in (headers.get('Permissions-Policy') or ''),
              f"val={headers.get('Permissions-Policy')}")
        check("A6 Server 指纹头移除",
              headers.get('Server') is None,
              f"val={headers.get('Server')}")
        check("A7 X-Powered-By 指纹头移除",
              headers.get('X-Powered-By') is None,
              f"val={headers.get('X-Powered-By')}")

        # A8：SECURITY_HEADERS=False 时不注入
        global_var.SECURITY_HEADERS = False
        r = client.get("/")
        check("A8 开关关闭时不注入安全头",
              r.headers.get('X-Content-Type-Options') is None,
              f"val={r.headers.get('X-Content-Type-Options')}")
        global_var.SECURITY_HEADERS = True

        # ============ B：会话 Cookie 加固 ============
        global_var.SESSION_COOKIE_SECURE = False
        r = do_login(client)
        set_cookies = r.headers.getlist("Set-Cookie")
        check("B1 登录成功 200", r.status_code == 200, f"status={r.status_code}")
        token_cookie = next((c for c in set_cookies if c.strip().startswith('token=')), '')
        csrf_cookie = next((c for c in set_cookies if c.strip().startswith('csrf_token=')), '')
        check("B2 token Cookie HttpOnly", 'HttpOnly' in token_cookie, f"raw={token_cookie[:60]}")
        check("B3 token Cookie SameSite=Lax", 'SameSite=Lax' in token_cookie, f"raw={token_cookie[:60]}")
        check("B4 Secure=False 时无 Secure 属性", 'Secure' not in token_cookie, f"raw={token_cookie[:60]}")
        check("B5 csrf_token Cookie 非 HttpOnly", 'HttpOnly' not in csrf_cookie, f"raw={csrf_cookie[:60]}")

        # B6：SECURE=True 联动
        global_var.SESSION_COOKIE_SECURE = True
        r = do_login(client)
        token_cookie2 = next((c for c in r.headers.getlist("Set-Cookie") if c.strip().startswith('token=')), '')
        check("B6 Secure=True 时 Cookie 带 Secure", 'Secure' in token_cookie2, f"raw={token_cookie2[:60]}")
        global_var.SESSION_COOKIE_SECURE = False

        # ============ C：会话空闲超时 ============
        r = do_login(client)
        body = r.get_json() or {}
        token = (body.get('data') or {}).get('token')
        check("C1 登录获取 token", bool(token), f"token={token[:8] if token else None}...")
        # 未超时：verify_token 有效并刷新 last_active_at
        user = auth.verify_token(token)
        check("C2 未超时会话有效", user is not None, f"user={user}")
        old_active = auth.sessions[token]['last_active_at']
        time.sleep(0.01)
        auth.verify_token(token)
        check("C3 有效请求刷新 last_active_at",
              auth.sessions[token]['last_active_at'] >= old_active,
              f"old={old_active} new={auth.sessions[token]['last_active_at']}")
        # 超时：人为把 last_active_at 拨回超时阈值之前
        idle = getattr(global_var, 'SESSION_IDLE_TIMEOUT', 1800)
        auth.sessions[token]['last_active_at'] = time.time() - idle - 60
        check("C4 空闲超时会话失效", auth.verify_token(token) is None,
              "verify_token 返回 None")
        check("C5 超时会话被清除", token not in auth.sessions, "sessions 已 pop")

        # ============ D：登录锁定 ip_username（默认） ============
        global_var.LOGIN_LOCK_MODE = 'ip_username'
        global_var.LOGIN_MAX_ATTEMPTS = 3  # 调小阈值加速测试
        global_var.LOGIN_LOCK_SECONDS = 300
        auth._login_attempts.clear()
        c1 = app.test_client()  # 独立客户端（隔离 Cookie）
        for i in range(3):
            r = do_login(c1, password="wrong")
            check(f"D{i+1} 第{i+1}次失败 401", r.status_code == 401, f"status={r.status_code}")
        # 第4次（密码正确）→ 锁定中 429 通用信息
        r = do_login(c1, password="admin123")
        check("D4 锁定期间（正确密码）返回 429", r.status_code == 429, f"status={r.status_code}")
        body = r.get_json() or {}
        check("D5 锁定返回通用错误信息", '尝试次数过多' in (body.get('message') or ''),
              f"msg={body.get('message')}")
        # 换 IP：不受影响，可正常登录
        c2 = app.test_client()
        r = do_login(c2, ip="10.1.2.3")
        check("D6 换 IP 不受锁定影响（ip_username 维度）", r.status_code == 200,
              f"status={r.status_code}")

        # ============ E：登录锁定 username（仅用户名维度） ============
        global_var.LOGIN_LOCK_MODE = 'username'
        global_var.LOGIN_MAX_ATTEMPTS = 3
        auth._login_attempts.clear()
        c3 = app.test_client()
        for _ in range(3):
            do_login(c3, password="wrong", ip="10.0.0.1")
        # 换 IP 同用户名 → 仍锁定
        c4 = app.test_client()
        r = do_login(c4, password="admin123", ip="10.0.0.2")
        check("E1 换 IP 仍锁定（username 维度）", r.status_code == 429, f"status={r.status_code}")
        check("E2 锁定期间错误信息不泄露锁定细节",
              '尝试次数过多' in ((r.get_json() or {}).get('message') or ''),
              f"msg={(r.get_json() or {}).get('message')}")

        # ============ F：登录锁定 off（禁用） ============
        global_var.LOGIN_LOCK_MODE = 'off'
        global_var.LOGIN_MAX_ATTEMPTS = 3
        auth._login_attempts.clear()
        c5 = app.test_client()
        for i in range(4):
            r = do_login(c5, password="wrong")
        check("F1 off 模式连续失败不锁定（第4次仍 401）", r.status_code == 401, f"status={r.status_code}")
        r = do_login(c5, password="admin123")
        check("F2 off 模式可正常登录", r.status_code == 200, f"status={r.status_code}")

        # ============ G：登录成功重置失败计数 ============
        global_var.LOGIN_LOCK_MODE = 'ip_username'
        global_var.LOGIN_MAX_ATTEMPTS = 3
        auth._login_attempts.clear()
        c6 = app.test_client()
        do_login(c6, password="wrong")          # 1 次失败
        do_login(c6, password="wrong")          # 2 次失败
        do_login(c6, password="admin123")       # 成功 → 重置
        r = do_login(c6, password="wrong")      # 失败重新计数（第1次，未达阈值）
        check("G1 成功登录后计数重置（再次失败 401 而非 429）", r.status_code == 401,
              f"status={r.status_code} attempts={auth._login_attempts}")

        print(f'\n==== 系统安全回归（v4.3.0）：共 {len(results)} 项，'
              f'通过 {sum(1 for _, c, _ in results if c)}，'
              f'失败 {sum(1 for _, c, _ in results if not c)} ====')
    finally:
        plugins.pop('auth', None)
        restore_fixtures()
        restore_global_var()

    ok = all(c for _, c, _ in results)
    sys.exit(0 if ok else 1)

if __name__ == '__main__':
    main()
