# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""阶段一权限体系验证脚本（Flask test_client，不启动真实服务）

场景：
A. auth 插件未安装 -> 可选鉴权，所有 API 放行
B. auth 插件已安装、未登录 -> /api/admin/* 401（验证致命漏洞已修复）、/api/auth/user/info 401
C. auth 已安装、管理员登录 -> /api/admin/* 200
D. auth 已安装、普通用户 -> /api/admin/* 403
E. login/logout 游客可访问（public）
F. 权限标记解析 _resolve_permission（新 @permission 与旧 require_role）
"""
import sys

sys.path.insert(0, _PROJECT_ROOT)

import app as appmod
from global_var import plugins
from core.permission import wrap_view_func

app = appmod.app
app.config["TESTING"] = True
client = app.test_client()

results = []

def check(name, cond, extra=""):
    status = "PASS" if cond else "FAIL"
    results.append((status, name, extra))
    print(f"[{status}] {name} {extra}")

# ============ 场景 A：auth 未安装（plugins 初始为空） ============
plugins.clear()

r = client.get("/api/admin/plugins")
check("A1 未安装auth-访问管理API", r.status_code == 200, f"status={r.status_code}")

r = client.get("/api/auth/user/info")
# auth 未安装时该路由不存在(plugin未加载)，走404；但说明不会被拦截器拦成401
check("A2 未安装auth-无401误拦截", r.status_code != 401, f"status={r.status_code}")

r = client.get("/")
check("A3 未安装auth-首页可访问", r.status_code == 200, f"status={r.status_code}")

# ============ 场景 B/C/D：安装 auth 插件 ============
# 手动加载 auth 插件并初始化（等价于 load_plugins 中启用分支）
import plugins.auth as auth_mod
auth = auth_mod.AuthPlugin()
auth.on_load()  # 初始化配置/默认管理员
# 手动注册路由包装（load_plugins 中启用插件时的核心动作）
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

plugins["auth"] = auth

# ---- B：未登录 ----
r = client.get("/api/auth/user/info")
check("B1 已安装auth-未登录访问user/info 401", r.status_code == 401, f"status={r.status_code}")

r = client.get("/api/admin/plugins")
check("B2 已安装auth-未登录访问admin API 401(漏洞修复)", r.status_code == 401, f"status={r.status_code} body={r.get_data(as_text=True)[:80]}")

r = client.get("/admin/plugins")
check("B3 已安装auth-未登录访问管理页 401/跳转", r.status_code in (401, 302), f"status={r.status_code}")

# ---- E：login public ----
r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
body = r.get_json()
admin_token = (body or {}).get("data", {}).get("token") if r.status_code == 200 else None
check("E1 login游客可访问返回token", r.status_code == 200 and bool(admin_token), f"status={r.status_code}")

# ---- C：管理员登录后 ----
# 从登录响应提取 csrf_token（阶段二 CSRF 双提交要求 POST 带 X-CSRF-Token）
_admin_csrf = None
for _c in r.headers.getlist("Set-Cookie"):
    if _c.strip().startswith("csrf_token="):
        _admin_csrf = _c.split(";", 1)[0].split("=", 1)[1]
headers = {"X-Token": admin_token, "X-CSRF-Token": _admin_csrf}
r = client.get("/api/auth/user/info", headers=headers)
check("C1 管理员token访问user/info 200", r.status_code == 200, f"status={r.status_code}")

r = client.get("/api/admin/plugins", headers=headers)
check("C2 管理员token访问admin API 200", r.status_code == 200, f"status={r.status_code}")

r = client.post("/api/auth/config", headers=headers,
                json={"SESSION_EXPIRE": 86400})
check("C3 管理员token更新config 200", r.status_code == 200, f"status={r.status_code}")

# ---- D：普通用户 ----
auth.create_user("user1", "pass123", role="user")
login_resp = client.post("/api/auth/login", json={"username": "user1", "password": "pass123"})
user_token = login_resp.get_json()["data"]["token"]
user_headers = {"X-Token": user_token}

r = client.get("/api/auth/user/info", headers=user_headers)
check("D1 普通用户访问user/info 200", r.status_code == 200, f"status={r.status_code}")

r = client.get("/api/admin/plugins", headers=user_headers)
check("D2 普通用户访问admin API 403", r.status_code == 403, f"status={r.status_code} body={r.get_data(as_text=True)[:60]}")

# ---- E2：logout public（未登录可登出，游客直接清除cookie） ----
r = client.post("/api/auth/logout")
check("E2 logout游客可访问", r.status_code == 200, f"status={r.status_code}")

# ============ F：_resolve_permission 标记解析 ============
from core.permission import _resolve_permission
from plugins.base_plugin import permission as perm
from plugins.base_plugin import BasePlugin

# 新版 @permission
@perm("public")
def f_public():
    pass

@perm("admin")
def f_admin():
    pass

def f_default():
    pass

# 旧版 require_role（在类定义时作用于未绑定函数，与真实插件一致）
def _m(self):
    pass

m_admin = BasePlugin.require_role(["admin"])(_m)
m_user = BasePlugin.require_role(["user"])(_m)
m_user_admin = BasePlugin.require_role(["user", "admin"])(_m)

# @permission 配合 @wraps 包装后的链解析
from functools import wraps

@wraps(f_admin)
def f_admin_wrapped():
    return f_admin()

check("F1 @permission public", _resolve_permission(f_public) == "public")
check("F2 @permission admin", _resolve_permission(f_admin) == "admin")
check("F3 无标记默认None", _resolve_permission(f_default) is None)
check("F4 require_role([admin]) -> admin", _resolve_permission(m_admin) == "admin")
check("F5 require_role([user]) -> user", _resolve_permission(m_user) == "user")
check("F6 require_role([user,admin]) -> user", _resolve_permission(m_user_admin) == "user")
check("F7 @permission 经 @wraps 链解析", _resolve_permission(f_admin_wrapped) == "admin")

# ============ 汇总 ============
fails = [x for x in results if x[0] == "FAIL"]
print("\n" + "=" * 50)
print(f"总计 {len(results)} 项，通过 {len(results) - len(fails)}，失败 {len(fails)}")
if fails:
    for f in fails:
        print("FAIL:", f[1], f[2])
    sys.exit(1)
print("ALL PASS")
