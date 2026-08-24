# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""插件重载后会话保持回归测试（test client 模式，无需外部服务）

背景：auth 会话文件非原子写导致 load_plugins 重载 auth 时可能读到空/截断文件，
引发 verify_token 失败（偶发 401）。修复为 .tmp + os.replace 原子写。

本测试验证：登录后触发 load_plugins 重载，重载后原登录会话仍有效（admin 接口 200）。
运行：python test_reload_race.py
"""
import sys

sys.path.insert(0, _PROJECT_ROOT)

import app as appmod
from core.plugin_loader import load_plugins

app = appmod.app
app.config["TESTING"] = True

# 初始化：加载插件（app.py 的 main 段才会调用 load_plugins，import 时不会）
load_plugins()

ROUNDS = 20
results = []


def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")


def get_csrf(client):
    try:
        return client.get_cookie('csrf_token')
    except Exception:
        return None


ok_rounds = 0
for i in range(1, ROUNDS + 1):
    c = app.test_client()
    r = c.post('/api/auth/login', json={'username': 'admin', 'password': 'admin123'})
    if r.status_code != 200:
        check(f'round{i} 登录', False, f'status={r.status_code}')
        continue
    token = r.get_json()['data']['token']
    csrf = get_csrf(c)
    headers = {'X-Token': token, 'X-CSRF-Token': csrf or ''}

    # 基线：登录后访问 admin
    r = c.get('/api/admin/plugins', headers=headers)
    if r.status_code != 200:
        check(f'round{i} 基线', False, f'status={r.status_code}')
        continue

    # 触发 load_plugins（重载 auth，模拟热加载/上传/更新后的重载）
    try:
        load_plugins()
    except Exception as e:
        check(f'round{i} 重载', False, f'{str(e)[:60]}')
        continue

    # 重载后立即访问 admin（验证原会话仍有效）
    r = c.get('/api/admin/plugins', headers=headers)
    if r.status_code != 200:
        check(f'round{i} 重载后会话', False, f'status={r.status_code} body={r.get_data(as_text=True)[:80]}')
        continue
    ok_rounds += 1

check(f'重载后会话保持 {ok_rounds}/{ROUNDS} 轮', ok_rounds == ROUNDS, f'ok={ok_rounds}')

passed = sum(1 for _, cond, _ in results if cond)
print(f"\n==== 重载竞态回归 共 {len(results)} 项，通过 {passed}，失败 {len(results) - passed} ====")
_os._exit(0 if passed == len(results) else 1)
