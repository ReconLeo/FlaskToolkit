# -*- coding: utf-8 -*-
"""自助注册 + 邀请码 + 审核回归（v4.10 M5，隔离目录）

场景：
A. 注册开关（默认关）
  A1 未开放时注册 → 403
B. 开启注册 + 无邀请码 → pending 待审核
  B1 注册成功返回 pending；B2 pending 登录 → 403 待审核提示
  B3 重复用户名 → 400；B4 密码过短 → 400
C. 邀请码
  C1 生成邀请码（FTK-XXXX-XXXX 格式）；C2 有效邀请码注册 → active
  C3 邀请码一次性（二次使用拒绝）；C4 无效邀请码 → 400；C5 撤销邀请码
D. 审核
  D1 pending_users 列表；D2 approve → 可登录；D3 reject → 删除
E. user_manage 管理 API（admin）
  E1 生成邀请码 API（含 register_url）；E2 邀请码列表；E3 待审列表
  E4 审核通过 API；E5 注册开关 API（/api/auth/config ALLOW_REGISTER）→ 生效

运行：python tests/test_register.py
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
_tmp = tempfile.mkdtemp(prefix='ftk_register_')
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


def main():
    try:
        # ============ 注入 auth + user_manage（内存配置，避免污染真实数据） ============
        from core.permission import wrap_view_func
        import plugins.auth as auth_mod
        auth = auth_mod.AuthPlugin()
        auth.config = {
            "SESSION_EXPIRE": 86400,
            "ALLOW_REGISTER": False,
            "users": [{
                "id": 1,
                "username": "admin",
                "password": auth._hash_password("admin123"),
                "nickname": "管理员",
                "role": "admin",
                "status": "active",
            }],
        }
        auth.SESSION_EXPIRE = 86400
        auth.sessions = {}
        auth._login_attempts = {}
        auth.save_config = lambda: True
        auth._save_sessions = lambda: None
        auth._wrapped_routes = {}
        for route in auth.routes:
            wrapped = wrap_view_func(route["view_func"], auth.name, route)
            path = route["path"]
            methods = tuple(route.get("methods", ["GET"]))
            auth._wrapped_routes.setdefault(path, {})[methods] = wrapped
        global_var.plugins["auth"] = auth

        import plugins.user_manage as um_mod
        um = um_mod.UserManagePlugin()
        um.auth_plugin = auth
        um._wrapped_routes = {}
        for route in um.routes:
            wrapped = wrap_view_func(route["view_func"], um.name, route)
            path = route["path"]
            methods = tuple(route.get("methods", ["GET"]))
            um._wrapped_routes.setdefault(path, {})[methods] = wrapped
        global_var.plugins["user_manage"] = um

        # ============ A. 注册开关默认关 ============
        r = client.post('/api/auth/register', json={"username": "alice", "password": "alice123"})
        check("A1 未开放注册 → 403", r.status_code == 403,
              f"status={r.status_code} msg={r.get_json().get('message') if r.is_json else ''}")

        # 开启注册
        auth.config["ALLOW_REGISTER"] = True

        # ============ B. 无邀请码 → pending ============
        r = client.post('/api/auth/register', json={"username": "bob", "password": "bob12345", "nickname": "鲍勃"})
        b = r.get_json()
        check("B1 无邀请码注册 → pending",
              r.status_code == 200 and b.get("data", {}).get("user", {}).get("status") == "pending",
              f"status={r.status_code} user={b.get('data', {}).get('user')}")

        r = client.post('/api/auth/login', json={"username": "bob", "password": "bob12345"})
        check("B2 pending 用户登录 → 403 待审核提示",
              r.status_code == 403 and "审核" in (r.get_json().get("message") or ""),
              f"status={r.status_code} msg={r.get_json().get('message') if r.is_json else ''}")

        r = client.post('/api/auth/register', json={"username": "bob", "password": "whatever1"})
        check("B3 重复用户名 → 400", r.status_code == 400, f"status={r.status_code}")

        r = client.post('/api/auth/register', json={"username": "shorty", "password": "123"})
        check("B4 密码过短 → 400", r.status_code == 400, f"status={r.status_code}")

        # ============ C. 邀请码 ============
        code_info = auth.create_invite_code(note="给卡罗尔")
        code = code_info["code"]
        check("C1 邀请码格式 FTK-XXXXXXXX-XXXX", len(code) == 17 and code.startswith('FTK-') and code.count('-') == 2,
              f"code={code}")

        r = client.post('/api/auth/register', json={"username": "carol", "password": "carol123", "invite_code": code})
        c = r.get_json()
        check("C2 有效邀请码注册 → active",
              r.status_code == 200 and c.get("data", {}).get("user", {}).get("status") == "active",
              f"status={r.status_code} user={c.get('data', {}).get('user')}")
        check("C2b 邀请码已标记使用", auth.list_invite_codes()[0]["used_by"] == "carol", '')

        r = client.post('/api/auth/register', json={"username": "carol2", "password": "carol234", "invite_code": code})
        check("C3 邀请码一次性（二次使用 → 400）", r.status_code == 400,
              f"status={r.status_code} msg={r.get_json().get('message') if r.is_json else ''}")

        r = client.post('/api/auth/register', json={"username": "dave", "password": "dave1234", "invite_code": "FTK-INVALID-0000"})
        check("C4 无效邀请码 → 400", r.status_code == 400, f"status={r.status_code}")

        check("C5 撤销邀请码", auth.revoke_invite_code(code) is True and len(auth.list_invite_codes()) == 0, '')

        # ============ D. 审核 ============
        pend = auth.pending_users()
        check("D1 pending_users 含 bob", any(u["username"] == "bob" for u in pend), f"list={[u['username'] for u in pend]}")

        bob_id = next(u["id"] for u in pend if u["username"] == "bob")
        check("D2 approve_user → active", auth.approve_user(bob_id) is True, '')
        r = client.post('/api/auth/login', json={"username": "bob", "password": "bob12345"})
        check("D2b 审核后 bob 可登录", r.status_code == 200, f"status={r.status_code}")

        # 再造一个 pending 用户测 reject
        client.post('/api/auth/register', json={"username": "eve", "password": "eve12345"})
        eve_id = next(u["id"] for u in auth.pending_users() if u["username"] == "eve")
        check("D3 reject_user → 删除", auth.reject_user(eve_id) is True
              and all(u["username"] != "eve" for u in auth.get_all_users()), '')

        # ============ E. user_manage 管理 API（admin） ============
        r = client.post('/api/auth/login', json={"username": "admin", "password": "admin123"})
        check("E0 admin 登录", r.status_code == 200, f"status={r.status_code}")
        csrf = client.get_cookie('csrf_token').value

        # E1 生成邀请码 API
        r = client.post('/api/user_manage/invite-code', json={"note": "发给Frank"},
                        headers={"X-CSRF-Token": csrf})
        e1 = r.get_json()
        check("E1 生成邀请码 API → 200 含 register_url",
              r.status_code == 200 and e1.get("data", {}).get("code", "").startswith('FTK-')
              and "/register?code=" in (e1.get("data", {}).get("register_url") or ""),
              f"data={e1.get('data')}")

        # E2 邀请码列表 API
        r = client.get('/api/user_manage/invite-codes', headers={"X-Token": client.get_cookie('token').value})
        check("E2 邀请码列表 API → 200", r.status_code == 200 and len(r.get_json().get("data", {}).get("list", [])) == 1,
              f"status={r.status_code}")

        # E3 待审列表 API（先注册一个 pending）
        client.post('/api/auth/register', json={"username": "grace", "password": "grace123"})
        r = client.get('/api/user_manage/pending-users', headers={"X-Token": client.get_cookie('token').value})
        check("E3 待审列表 API 含 grace",
              r.status_code == 200 and any(u["username"] == "grace" for u in r.get_json().get("data", {}).get("list", [])),
              f"status={r.status_code}")

        # E4 审核通过 API
        grace_id = next(u["id"] for u in auth.pending_users() if u["username"] == "grace")
        r = client.post('/api/user_manage/user/approve', json={"user_id": grace_id},
                        headers={"X-CSRF-Token": csrf})
        check("E4 审核通过 API → 200", r.status_code == 200, f"status={r.status_code}")

        # E5 注册开关 API（关闭 → 注册 403）
        r = client.post('/api/auth/config', json={"ALLOW_REGISTER": False},
                        headers={"X-CSRF-Token": csrf})
        check("E5a 开关 API 返回 200", r.status_code == 200
              and r.get_json().get("data", {}).get("ALLOW_REGISTER") is False, f"status={r.status_code}")
        r = client.post('/api/auth/register', json={"username": "heidi", "password": "heidi123"})
        check("E5b 关闭后注册 → 403", r.status_code == 403, f"status={r.status_code}")
        r = client.post('/api/auth/config', json={"ALLOW_REGISTER": True},
                        headers={"X-CSRF-Token": csrf})
        r = client.post('/api/auth/register', json={"username": "heidi", "password": "heidi123"})
        check("E5c 重新开启后注册 → pending 200",
              r.status_code == 200 and r.get_json().get("data", {}).get("user", {}).get("status") == "pending",
              f"status={r.status_code}")

        # ============ F. 邀请码管理 API ============
        r = client.post('/api/user_manage/invite-code/revoke', json={"code": e1["data"]["code"]},
                        headers={"X-CSRF-Token": csrf})
        check("F1 撤销邀请码 API → 200", r.status_code == 200, f"status={r.status_code}")
        r = client.get('/api/user_manage/invite-codes', headers={"X-Token": client.get_cookie('token').value})
        check("F2 撤销后列表为空", len(r.get_json().get("data", {}).get("list", [])) == 0, '')

        print(f'\n==== 自助注册 + 邀请码 + 审核（v4.10 M5）：共 {len(results)} 项，'
              f'通过 {sum(1 for _, c, _ in results if c)}，'
              f'失败 {sum(1 for _, c, _ in results if not c)} ====')
    finally:
        global_var.plugins.pop('auth', None)
        global_var.plugins.pop('user_manage', None)

    ok = all(c for _, c, _ in results)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
