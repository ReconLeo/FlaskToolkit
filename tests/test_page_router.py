# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""大插件多模板（页面路由 page=True）回归测试
隔离目录（mock 全部路径到 /tmp）+ 手动加载多模板测试插件 + test_client。

覆盖：
- _resolve_template：正斜杠模板名（Jinja 不认反斜杠）、命名空间优先、旧式回退、不存在返回 None
- render() 助手：返回 Response（可直接 return 作为页面响应），上下文注入正确
- 主入口自动检测：命名空间 index.html（回退 <name>.html）
- 子页面分发：dict → 渲染命名空间模板；Response → 原样返回；路径参数注入 kwargs
- 404：不存在的子页面
- 权限层不破坏页面路由（可选鉴权未装时放行，public/user 均可访问）
运行：python tests/test_page_router.py
"""
import json
import os
import shutil
import sys
import tempfile

# ---------- 隔离目录 ----------
_isolated = tempfile.mkdtemp(prefix='ftk_pager_')
for sub in ('plugins/configs', 'plugins/data', 'temp',
            'templates/plugins/demo'):
    os.makedirs(os.path.join(_isolated, sub), exist_ok=True)

import global_var

_SAVED = {}
for _attr, _val in (
        ('BASE_DIR', _isolated),
        ('UPLOAD_TEMP_DIR', os.path.join(_isolated, 'temp')),
        ('FRONTEND_TEMPLATE_DIR', os.path.join(_isolated, 'templates', 'frontend_tools')),
        ('FRONTEND_CONFIG_FILE', os.path.join(_isolated, 'frontend_tools.json')),
        ('STATS_FILE', os.path.join(_isolated, 'data', 'stats.json')),
        ('PLUGIN_CONFIGS_DIR', os.path.join(_isolated, 'plugins', 'configs')),
):
    _SAVED[_attr] = getattr(global_var, _attr, None)
    setattr(global_var, _attr, _val)

import app as appmod
from core.permission import wrap_view_func, wrap_page_func

app = appmod.app
app.config["TESTING"] = True

# 模板加载：隔离目录 templates 优先（插件模板命名空间），真实 templates 兜底（基础页面 404 等）
from jinja2 import ChoiceLoader, FileSystemLoader
app.jinja_env.loader = ChoiceLoader([
    FileSystemLoader(os.path.join(_isolated, 'templates')),
    FileSystemLoader(os.path.join(_PROJECT_ROOT, 'templates')),
])

# ---------- 多模板测试插件（模拟 loader 的 _wrapped_pages 注册） ----------
from plugins.base_plugin import BasePlugin, permission as permission_required

class Demo(BasePlugin):
    name = "demo"
    title = "多模板示例"
    description = "页面路由测试"
    version = "1.0.0"
    author = "T"
    category = "测试"
    permission = "user"

    @property
    def routes(self):
        return [
            {"path": "/status", "name": "状态子页", "methods": ["GET"],
             "page": True, "template": "status.html", "view_func": self.page_status},
            {"path": "/about", "name": "关于子页", "methods": ["GET"],
             "page": True, "template": "about.html", "view_func": self.page_about},
            {"path": "/user/<username>", "name": "用户子页", "methods": ["GET"],
             "page": True, "template": "user.html", "view_func": self.page_user},
        ]

    def render_index(self):
        return {"greeting": "hello demo", "name": self.name}

    @permission_required("public")
    def page_status(self):
        return {"data": "status data from view"}

    def page_about(self):
        return self.render("about.html", message="about via render helper")

    def page_user(self, username):
        return {"username": username}

class NoNamePlugin(BasePlugin):
    """纯 API 路由插件（routes 无 name 键、无主模板、无 page()）——
    回归漏洞：/plugin/<name> 调试页 route['name'] KeyError 500"""
    name = "noname"
    title = "无名称路由插件"
    description = "纯 API 路由，name 字段缺失"
    version = "1.0.0"
    author = "T"
    category = "测试"
    permission = "user"

    @property
    def routes(self):
        return [
            {"path": "/pure", "methods": ["GET"], "view_func": self.pure_api},
            {"path": "/data/<int:pid>", "methods": ["POST"], "view_func": self.data_api},
        ]

    def pure_api(self):
        return self.success_response(data={"ok": True})

    def data_api(self, pid):
        return self.success_response(data={"pid": pid})

# 模拟 loader：page 路由 → _wrapped_pages（path -> view_func/template）
_plugin = Demo()
_plugin._wrapped_pages = {}
for _r in _plugin.routes:
    _tpl = _r.get('template') or (_r['path'].strip('/').rsplit('/', 1)[-1] + '.html')
    _plugin._wrapped_pages[_r['path']] = {
        'view_func': wrap_view_func(_r['view_func'], _plugin.name, _r),
        'template': _tpl,
    }
# 主入口（loader 同样会设置 _wrapped_page）
_plugin._wrapped_page = wrap_page_func(_plugin.render_plugin_page, _plugin.name)
global_var.plugins[_plugin.name] = _plugin

# 纯 API 插件（无 name 键）只设主入口，验证调试页容错
_noname = NoNamePlugin()
_noname._wrapped_page = wrap_page_func(_noname.render_plugin_page, _noname.name)
global_var.plugins[_noname.name] = _noname

# ---------- 模板文件写入隔离目录 ----------
_Tpl = os.path.join(_isolated, 'templates', 'plugins', 'demo')
open(os.path.join(_Tpl, 'index.html'), 'w', encoding='utf-8').write(
    '<h1>Home</h1><p>{{ greeting }}</p><p>{{ plugin.name }}</p>')
open(os.path.join(_Tpl, 'status.html'), 'w', encoding='utf-8').write('<h1>Status</h1><p>{{ data }}</p>')
open(os.path.join(_Tpl, 'about.html'), 'w', encoding='utf-8').write('<h1>About</h1><p>{{ message }}</p>')
open(os.path.join(_Tpl, 'user.html'), 'w', encoding='utf-8').write('<h1>User</h1><p>{{ username }}</p>')
# 旧式单模板（plugins/ 根目录回退）
open(os.path.join(_isolated, 'templates', 'plugins', 'legacy.html'), 'w', encoding='utf-8').write(
    '<h1>Legacy</h1><p>{{ legacy }}</p>')
# 子目录模板（验证反斜杠模板名归一化）
os.makedirs(os.path.join(_Tpl, 'sub'), exist_ok=True)
open(os.path.join(_Tpl, 'sub', 'about.html'), 'w', encoding='utf-8').write('<h1>SubAbout</h1>')

results = []

def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

def main():
    try:
        client = app.test_client()

        # ============ 1. _resolve_template：正斜杠 + 命名空间 + 回退 ============
        # 单元级（依赖 current_app，需 app context）
        with app.app_context():
            r = _plugin._resolve_template('index.html')
            check('1 命名空间 index.html 解析为正斜杠模板名',
                  r == 'plugins/demo/index.html', f'got={r!r}')
            r = _plugin._resolve_template('missing.html')
            check('1 不存在的模板返回 None', r is None, f'got={r!r}')
            # 旧式回退：命名空间无 legacy.html → plugins/legacy.html
            r = _plugin._resolve_template('legacy.html')
            check('1 旧式 plugins/ 根目录回退',
                  r == 'plugins/legacy.html', f'got={r!r}')
            # 传入含反斜杠的模板名也能归一化（Jinja 模板名须为正斜杠）
            r = _plugin._resolve_template('sub\\about.html')
            check('1 反斜杠模板名归一化为正斜杠', r == 'plugins/demo/sub/about.html', f'got={r!r}')

            # ============ 2. render() 助手：返回 Response + 上下文注入 ============
            resp = _plugin.render('about.html', message='injected')
            check('2 render() 返回 Response', isinstance(resp, _import_Response()),
                  f'type={type(resp).__name__}')
            body = resp.get_data(as_text=True)
            check('2 render() 上下文注入生效', 'injected' in body, f'body={body.strip()!r}')
            # 不存在的模板抛 ValueError
            try:
                _plugin.render('no_tpl.html')
                check('2 render() 缺失模板抛 ValueError', False, '未抛异常')
            except ValueError:
                check('2 render() 缺失模板抛 ValueError', True, '')

        # ============ 3. 主入口自动检测 index.html ============
        r = client.get('/plugin/demo', follow_redirects=False)
        t = r.get_data(as_text=True)
        check('3 主入口 /plugin/demo 200', r.status_code == 200, f'status={r.status_code}')
        check('3 主入口渲染命名空间 index.html',
              'Home' in t and 'hello demo' in t and 'demo' in t, t[:120])

        # ============ 4. 子页面分发：dict -> 模板 ============
        r = client.get('/plugin/demo/status')
        t = r.get_data(as_text=True)
        check('4 dict 子页面 status 200', r.status_code == 200, f'status={r.status_code}')
        check('4 status 渲染 status.html + dict 数据',
              'Status' in t and 'status data from view' in t, t[:120])

        # ============ 5. 子页面分发：Response 原样返回 ============
        r = client.get('/plugin/demo/about')
        t = r.get_data(as_text=True)
        check('5 Response 子页面 about 200', r.status_code == 200, f'status={r.status_code}')
        check('5 about 渲染 + render 助手数据',
              'About' in t and 'about via render helper' in t, t[:120])

        # ============ 6. 子页面分发：路径参数注入 ============
        r = client.get('/plugin/demo/user/alice')
        t = r.get_data(as_text=True)
        check('6 路径参数子页面 user/alice 200', r.status_code == 200, f'status={r.status_code}')
        check('6 路径参数注入 username',
              'User' in t and 'alice' in t, t[:120])

        # ============ 7. 404：不存在的子页面 ============
        r = client.get('/plugin/demo/nonexist')
        check('7 不存在子页面 404', r.status_code == 404, f'status={r.status_code}')

        # ============ 8. 权限层不破坏页面路由（可选鉴权未装 → 放行） ============
        r = client.get('/plugin/demo/status')  # public
        check('8 public 页面未登录可访问', r.status_code == 200, f'status={r.status_code}')
        r = client.get('/plugin/demo/user/alice')  # 默认 user，auth 未装放行
        check('8 user 页面 auth 未装放行', r.status_code == 200, f'status={r.status_code}')

        # ============ 9. 纯 API 路由插件（routes 无 name 键）→ 调试页 200 ============
        # 回归：route['name'] 强访问 KeyError → /plugin/<name> 500
        r = client.get('/plugin/noname')
        t = r.get_data(as_text=True)
        check('9 纯 API 无 name 插件调试页 200（不再 500）',
              r.status_code == 200, f'status={r.status_code}')
        check('9 调试页渲染 API 列表（name 回退为 path）',
              '/api/noname/pure' in t and '/api/noname/data' in t, t[:120])
        # 路径参数占位符识别（<int:pid>）不报错
        check('9 路径参数占位符解析不报错', 'pid' in t or r.status_code == 200, '')

        print(f'\n==== 大插件多模板（页面路由）回归：共 {len(results)} 项，'
              f'通过 {sum(1 for _, c, _ in results if c)}，'
              f'失败 {sum(1 for _, c, _ in results if not c)} ====')
    finally:
        global_var.plugins.pop(_plugin.name, None)
        global_var.plugins.pop(_noname.name, None)
        for _attr, _val in _SAVED.items():
            setattr(global_var, _attr, _val)
        try:
            shutil.rmtree(_isolated, ignore_errors=True)
        except Exception:
            pass

    ok = all(c for _, c, _ in results)
    sys.exit(0 if ok else 1)


def _import_Response():
    from flask import Response
    return Response


if __name__ == '__main__':
    main()
