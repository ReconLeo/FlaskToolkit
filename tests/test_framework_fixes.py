# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""框架小修复回归（v4.2.1 累计更新）

场景：
A. auth 未装 → /plugin/* 页面可选鉴权放行（200）
B. auth 已装 + 插件 public_page=True → /plugin/<name> 页面免登录（200，interceptor 豁免）
C. auth 已装 + 普通插件 → /plugin/<name> 页面仍守卫（302 跳登录）
D. plugin_common.js 双重 CSRF 注入修复：setRequestHeader('X-CSRF-Token') 全文件恰 1 处（
   全局 XHR send 拦截单次注入；request() 不再手动注入，避免同名头逗号拼接 403）
运行：python tests/test_framework_fixes.py
"""
import os
import sys

sys.path.insert(0, _PROJECT_ROOT)

import app as appmod
from global_var import plugins
from core.permission import wrap_page_func, wrap_view_func

app = appmod.app
app.config["TESTING"] = True
client = app.test_client()

results = []

def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

# ============ 测试插件 ============
from plugins.base_plugin import BasePlugin

class PublicPagePlugin(BasePlugin):
    name = "pubpage"
    title = "公开页面插件"
    description = "public_page=True 页面免登录"
    version = "1.0.0"
    author = "T"
    category = "测试"
    permission = "public"
    public_page = True  # interceptor 豁免开关

    @property
    def routes(self):
        return []

class NormalPlugin(BasePlugin):
    name = "normal"
    title = "普通插件"
    description = "默认受页面登录守卫"
    version = "1.0.0"
    author = "T"
    category = "测试"
    permission = "user"

    @property
    def routes(self):
        return []

def register_plugin(inst):
    inst._wrapped_page = wrap_page_func(inst.render_plugin_page, inst.name)
    plugins[inst.name] = inst

def main():
    try:
        pub = PublicPagePlugin()
        normal = NormalPlugin()
        plugins.clear()

        # ============ A：auth 未装 → 可选鉴权，全部放行 ============
        register_plugin(pub)
        register_plugin(normal)
        r = client.get("/plugin/pubpage")
        check("A1 auth未装-public_page插件页面放行", r.status_code == 200, f"status={r.status_code}")
        r = client.get("/plugin/normal")
        check("A2 auth未装-普通插件页面放行", r.status_code == 200, f"status={r.status_code}")

        # ============ 安装 auth（等价 load_plugins 启用分支） ============
        import plugins.auth as auth_mod
        auth = auth_mod.AuthPlugin()
        auth.on_load()
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

        # ============ B：auth 已装 + public_page=True → 页面免登录 ============
        r = client.get("/plugin/pubpage")
        check("B1 public_page=True 页面免登录 200", r.status_code == 200, f"status={r.status_code}")

        # ============ C：auth 已装 + 普通插件 → 页面守卫跳登录 ============
        r = client.get("/plugin/normal")
        check("C1 普通插件页面仍守卫 302", r.status_code == 302, f"status={r.status_code}")
        check("C2 重定向到登录页", '/login' in (r.headers.get('Location') or ''), f"loc={r.headers.get('Location')}")

        # ============ D：plugin_common.js 双重 CSRF 注入修复（源码静态断言） ============
        js_path = os.path.join(_PROJECT_ROOT, 'static', 'js', 'plugin_common.js')
        js = open(js_path, 'r', encoding='utf-8').read()
        # request() 移除手动注入后，全文件 XHR 注入恰 1 处（全局 send 拦截）
        n_xhr = js.count("setRequestHeader('X-CSRF-Token'")
        check("D1 X-CSRF-Token 注入恰 1 处（无双重注入）", n_xhr == 1, f"count={n_xhr}")
        # fetch 拦截仍有条件注入（防重复）
        check("D2 fetch 拦截保留防重复判断",
              "init.headers.has('X-CSRF-Token')" in js and "init.headers.set('X-CSRF-Token'" in js, '')
        # request() 方法内不再手动注入 CSRF 头（Content-Type 等普通头不受影响）
        req_start = js.find('request: function(options)')
        req_end = js.find('\n    }', req_start)
        req_body = js[req_start:req_end] if req_start != -1 else ''
        check("D3 request() 不再手动注入 X-CSRF-Token", "setRequestHeader('X-CSRF-Token'" not in req_body, '')
        # 全局 XHR send 拦截保留（单次注入所在）
        check("D4 全局 XHR send 拦截保留", 'XMLHttpRequest.prototype.send' in js and "setRequestHeader('X-CSRF-Token'" in js, '')

        print(f'\n==== 框架小修复回归（public_page 豁免 + CSRF 单值注入）：共 {len(results)} 项，'
              f'通过 {sum(1 for _, c, _ in results if c)}，'
              f'失败 {sum(1 for _, c, _ in results if not c)} ====')
    finally:
        plugins.pop('pubpage', None)
        plugins.pop('normal', None)
        plugins.pop('auth', None)

    ok = all(c for _, c, _ in results)
    sys.exit(0 if ok else 1)

if __name__ == '__main__':
    main()
