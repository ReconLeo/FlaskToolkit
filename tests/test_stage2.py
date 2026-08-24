# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""阶段二后端验证：
A 密码哈希（PBKDF2）、HttpOnly token Cookie + csrf_token Cookie
B 阶段一权限回归（三层权限仍正常）
C CSRF 双提交校验
D C组修复（禁用插件 404、/403 路由、login 空 body 400）
"""
import sys, os, re, json

sys.path.insert(0, _PROJECT_ROOT)

import app as appmod
from global_var import plugins
from core.permission import wrap_view_func

app = appmod.app
app.config["TESTING"] = True
client = app.test_client()

results = []

def check(name, cond, extra=""):
    results.append(("PASS" if cond else "FAIL", name, extra))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")

def all_set_cookies(response):
    """获取响应所有 Set-Cookie 头（Flask3 多条是独立 header）"""
    return response.headers.getlist("Set-Cookie")


def csrf_from_setcookie(set_cookie_list):
    """从 Set-Cookie 头列表解析 csrf_token 值"""
    for c in set_cookie_list:
        if c.strip().startswith("csrf_token="):
            return c.split(";", 1)[0].split("=", 1)[1]
    return None

# ============ 加载 auth 插件（模拟 load_plugins 启用分支） ============
plugins.clear()
import plugins.auth as auth_mod
auth = auth_mod.AuthPlugin()
auth.on_load()
for route in auth.routes:
    wrapped = wrap_view_func(route["view_func"], auth.name, route)
    if not hasattr(auth, "_wrapped_routes"):
        auth._wrapped_routes = {}
    path = route["path"]
    methods = tuple(route.get("methods", ["GET"]))
    if path not in auth._wrapped_routes:
        auth._wrapped_routes[path] = {}
    auth._wrapped_routes[path][methods] = wrapped
plugins["auth"] = auth

# ---- A1 密码哈希 ----
cfg_path = os.path.join(_PROJECT_ROOT, 'plugins', 'configs', 'auth.json')
with open(cfg_path, "r", encoding="utf-8") as f:
    cfg = json.load(f)
admin = [u for u in cfg["users"] if u["username"] == "admin"][0]
check("A1 默认admin密码为PBKDF2格式", admin["password"].startswith("pbkdf2_sha256$"),
      f"prefix={admin['password'][:16]}...")
check("A1 配置不含XOR_KEY", "XOR_KEY" not in cfg)

# ---- A2 登录：HttpOnly token + csrf_token cookie ----
r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
check("A2 登录成功", r.status_code == 200, f"status={r.status_code}")
set_cookie_list = all_set_cookies(r)
token_cookie = next((c for c in set_cookie_list if c.strip().startswith("token=")), "")
csrf_cookie = next((c for c in set_cookie_list if c.strip().startswith("csrf_token=")), "")
check("A2 token Cookie HttpOnly", "HttpOnly" in token_cookie, f"cookie={token_cookie[:40]}")
check("A2 csrf_token Cookie 非HttpOnly", bool(csrf_cookie) and "HttpOnly" not in csrf_cookie,
      f"cookie={csrf_cookie[:40]}")
csrf = csrf_from_setcookie(set_cookie_list)
check("A2 csrf_token 已下发", bool(csrf), f"csrf={csrf[:8] if csrf else None}...")

# ---- B 权限回归（用未登录的全新 client） ----
anon = app.test_client()
check("B1 未登录访问admin API 401", anon.get("/api/admin/plugins").status_code == 401)
check("B2 未登录访问user/info 401", anon.get("/api/auth/user/info").status_code == 401)
# 登录后 cookie 自动携带，GET 无需 CSRF
check("B3 登录后GET admin API 200", client.get("/api/admin/plugins").status_code == 200)
check("B4 登录后GET user/info 200", client.get("/api/auth/user/info").status_code == 200)

# 普通用户
auth.create_user("user1", "pass123", role="user")
client2 = app.test_client()
client2.post("/api/auth/login", json={"username": "user1", "password": "pass123"})
check("B5 普通用户GET admin API 403", client2.get("/api/admin/plugins").status_code == 403)

# ---- C CSRF 校验 ----
# 已登录 client（admin）POST 不带 csrf 头 -> 403
r = client.post("/api/auth/config", json={"SESSION_EXPIRE": 86400})
check("C1 POST不带X-CSRF-Token 403", r.status_code == 403, f"status={r.status_code}")
# 带正确 csrf 头 -> 200
r = client.post("/api/auth/config", json={"SESSION_EXPIRE": 86400},
                headers={"X-CSRF-Token": csrf})
check("C2 POST带正确X-CSRF-Token 200", r.status_code == 200, f"status={r.status_code}")
# 错误 csrf -> 403
r = client.post("/api/auth/config", json={"SESSION_EXPIRE": 86400},
                headers={"X-CSRF-Token": "wrong-token"})
check("C3 POST带错误X-CSRF-Token 403", r.status_code == 403, f"status={r.status_code}")

# ---- D C组修复 ----
# D1 禁用插件访问 -> 404（不再500）
auth.enabled = False
r = client.get("/api/auth/user/info")
check("D1 禁用插件API 404非500", r.status_code == 404, f"status={r.status_code}")
r = client.get("/plugin/auth")
check("D2 禁用插件页面 404非500", r.status_code == 404, f"status={r.status_code}")
auth.enabled = True

# D3 /403 路由
r = client.get("/403")
check("D3 /403路由返回403页面", r.status_code == 403 and "403" in r.get_data(as_text=True),
      f"status={r.status_code}")

# D4/D5 login 空 body/缺密码：error_response 返回 body.code=400（HTTP 状态为200，属已知既有缺陷，检查 body code）
r = client.post("/api/auth/login", json={})
check("D4 login空body body.code=400", (r.get_json() or {}).get("code") == 400,
      f"body={(r.get_json() or {}).get('code')}")
r = client.post("/api/auth/login", json={"username": "admin"})
check("D5 login缺密码 body.code=400", (r.get_json() or {}).get("code") == 400,
      f"body={(r.get_json() or {}).get('code')}")

# ---- 汇总 ----
fails = [x for x in results if x[0] == "FAIL"]
print("\n" + "=" * 50)
print(f"总计 {len(results)} 项，通过 {len(results) - len(fails)}，失败 {len(fails)}")
for f_ in fails:
    print("FAIL:", f_[1], f_[2])
sys.exit(1 if fails else 0)
