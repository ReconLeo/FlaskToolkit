# -*- coding: utf-8 -*-
"""界面主题（深色模式）回归（v4.19，隔离目录）

场景：
A. core.theme 能力
  A1 available_themes 含 auto/light/dark
  A2 resolve_theme 白名单：合法主题原样，非法/未知回退 auto
  A3 resolve_theme 防注入：hack/../auto 之类非法值回退 auto
  A4 resolve_effective_theme：light/dark 实际值，auto/非法交前端解析

B. /theme 路由
  B1 GET /theme/dark?next=/ → 302 到 /，设置 theme=dark Cookie
  B2 GET /theme/light → Cookie theme=light
  B3 非法主题 GET /theme/hack → 302 + Cookie 为 auto（回退）
  B4 开放重定向防护：next=//evil.com 或 https://evil.com → 回退到 /

C. 上下文注入
  C1 公开页 <html data-theme-init> 存在，默认 auto
  C2 Cookie theme=dark 时 data-theme-init=dark
  C3 登录页含主题入口链接与词条

运行：python tests/test_theme.py
"""
import json
import os
import sys
import tempfile

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_TESTS_DIR)
sys.path.insert(0, _PROJECT_ROOT)

import global_var
_tmp = tempfile.mkdtemp(prefix='ftk_theme_')
_path_patches = {
    'BASE_DIR': _tmp,
    'USER_CONFIG_FILE': os.path.join(_tmp, 'data', 'user_config.json'),
    'STATS_FILE': os.path.join(_tmp, 'data', 'stats.json'),
    'PLUGIN_CONFIGS_DIR': os.path.join(_tmp, 'plugins', 'configs'),
    'PLUGIN_TEMP_DIR': os.path.join(_tmp, 'plugins', 'temp'),
    'LOG_DIR': os.path.join(_tmp, 'logs'),
    'UPLOAD_TEMP_DIR': os.path.join(_tmp, 'temp'),
    'PLUGIN_CACHE_DIR': os.path.join(_tmp, '.plugin_cache'),
    'PLUGIN_CACHE_FILE': os.path.join(_tmp, '.plugin_cache', 'plugin_discovery_cache.json'),
    'THEMES_DIR': os.path.join(_tmp, 'themes'),  # v4.19.2 可扩展主题目录
}
for _k, _v in _path_patches.items():
    setattr(global_var, _k, _v)
os.makedirs(os.path.join(_tmp, 'data'), exist_ok=True)
import shutil
# 隔离主题目录 + 内置 sepia 示例主题（v4.19.2）
shutil.copytree(os.path.join(_PROJECT_ROOT, 'themes', 'sepia'),
                os.path.join(_tmp, 'themes', 'sepia'))
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
    from core import theme

    av = theme.available_themes()
    check("A1 available_themes 含 auto/light/dark",
          {'auto', 'light', 'dark'} <= set(av), f"keys={list(av)}")
    check("A2 resolve_theme 合法原样 + 未知回退 auto",
          theme.resolve_theme('dark') == 'dark' and theme.resolve_theme('xxx') == 'auto', '')
    check("A3 resolve_theme 防注入",
          theme.resolve_theme('../dark') == 'auto' and theme.resolve_theme('hack') == 'auto', '')
    check("A4 resolve_effective_theme light/dark/auto/非法",
          theme.resolve_effective_theme('light') == 'light'
          and theme.resolve_effective_theme('dark') == 'dark'
          and theme.resolve_effective_theme('auto') == 'auto'
          and theme.resolve_effective_theme('hack') == 'auto',
          'light/dark 实际值，auto/非法交前端')

    r = client.get('/theme/dark?next=/', follow_redirects=False)
    ck = client.get_cookie('theme')
    check("B1 /theme/dark → 302 + theme=dark",
          r.status_code == 302 and ck and ck.value == 'dark',
          f"status={r.status_code} cookie={ck.value if ck else None}")
    client.set_cookie('theme', 'light', domain='localhost', path='/')
    r = client.get('/theme/light', follow_redirects=False)
    ck = client.get_cookie('theme')
    check("B2 /theme/light → theme=light", r.status_code == 302 and ck and ck.value == 'light',
          f"cookie={ck.value if ck else None}")
    client.set_cookie('theme', 'xxx', domain='localhost', path='/')
    r = client.get('/theme/hack', follow_redirects=False)
    ck = client.get_cookie('theme')
    check("B3 非法主题回退 auto", r.status_code == 302 and ck and ck.value == 'auto',
          f"cookie={ck.value if ck else None}")
    r = client.get('/theme/dark?next=https://evil.com', follow_redirects=False)
    loc = r.headers.get('Location') or ''
    check("B4 开放重定向防护回退 /", r.status_code == 302 and loc == '/', f"loc={loc}")

    client.set_cookie('theme', 'auto', domain='localhost', path='/')
    r = client.get('/login')
    body = r.get_data(as_text=True)
    check("C1 公开页 data-theme-init=auto", 'data-theme-init="auto"' in body, '')
    client.set_cookie('theme', 'dark', domain='localhost', path='/')
    r = client.get('/login')
    body = r.get_data(as_text=True)
    check("C2 Cookie dark → data-theme-init=dark", 'data-theme-init="dark"' in body, '')
    r = client.get('/login')
    lb = r.get_data(as_text=True)
    check("C3 登录页含主题入口链接", '/theme/dark' in lb and '跟随系统' in lb, '')

    # ===== v4.19.2 可扩展主题（themes/ 目录扫描）=====
    av = theme.available_themes()
    check("A5 available_themes 扫描到自定义 sepia", 'sepia' in av and av['sepia'] == 'Sepia',
          f"keys={sorted(av)}")
    # 非法目录名 / 缺 theme.json 不纳入
    os.makedirs(os.path.join(global_var.THEMES_DIR, 'bad dir'), exist_ok=True)
    os.makedirs(os.path.join(global_var.THEMES_DIR, 'nodata'), exist_ok=True)
    theme._scan_cache = {'key': None, 'themes': None}
    av2 = theme.available_themes()
    check("A6 非法名/缺声明目录被忽略",
          'sepia' in av2 and 'bad dir' not in av2 and 'nodata' not in av2,
          f"keys={sorted(av2)}")
    # 运行期新增主题生效（mtime 缓存失效）
    os.makedirs(os.path.join(global_var.THEMES_DIR, 'ocean'), exist_ok=True)
    with open(os.path.join(global_var.THEMES_DIR, 'ocean', 'theme.json'), 'w', encoding='utf-8') as f:
        json.dump({'name': 'ocean', 'title': 'Ocean'}, f)
    theme._scan_cache = {'key': None, 'themes': None}
    check("A7 运行期新增主题生效", 'ocean' in theme.available_themes(),
          f"keys={sorted(theme.available_themes())}")
    # get_theme_css
    css = theme.get_theme_css('sepia')
    check("A8 get_theme_css 读自定义主题", css is not None and 'sepia' in css and 'color-scheme' in css, '')
    check("A8b get_theme_css 白名单/内建/不存在拒绝",
          theme.get_theme_css('../dark') is None and theme.get_theme_css('dark') is None
          and theme.get_theme_css('nope') is None, '')
    # 动态白名单解析
    check("A9 resolve_theme 动态含自定义",
          theme.resolve_theme('sepia') == 'sepia' and theme.resolve_theme('ocean') == 'ocean'
          and theme.resolve_theme('deleted') == 'auto', '')
    check("A10 resolve_effective_theme 自定义返回声明名，被删回退 auto",
          theme.resolve_effective_theme('sepia') == 'sepia'
          and theme.resolve_effective_theme('deleted') == 'auto'
          and theme.resolve_effective_theme('auto') == 'auto', '')
    # get_theme 兜底：Cookie=自定义有效返回；被删回退 auto 且 Cookie 保留
    with app.test_request_context('/', headers={'Cookie': 'theme=sepia'}):
        check("A11 get_theme Cookie 自定义有效返回", theme.get_theme() == 'sepia',
              f"got={theme.get_theme()}")
    with app.test_request_context('/', headers={'Cookie': 'theme=deleted'}):
        check("A11b get_theme 被删主题回退 auto（Cookie 保留）",
              theme.get_theme() == 'auto', f"got={theme.get_theme()}")
    # /theme/<code> 切换自定义 + /theme-static 服务
    client.set_cookie('theme', 'sepia', domain='localhost', path='/')
    r = client.get('/theme/sepia?next=/', follow_redirects=False)
    ck = client.get_cookie('theme')
    check("B5 /theme/sepia → Cookie=sepia", r.status_code == 302 and ck and ck.value == 'sepia',
          f"cookie={ck.value if ck else None}")
    client.set_cookie('theme', 'auto', domain='localhost', path='/')
    r = client.get('/theme-static/sepia/theme.css')
    check("B6 /theme-static/sepia/theme.css 200 + CSS",
          r.status_code == 200 and 'sepia' in r.get_data(as_text=True), f"status={r.status_code}")
    r = client.get('/theme-static/hack/theme.css')
    check("B7 /theme-static 非法名 404", r.status_code == 404, f"status={r.status_code}")
    r = client.get('/theme-static/dark/theme.css')
    check("B7b /theme-static 内建主题 404", r.status_code == 404, f"status={r.status_code}")
    # 上下文注入 data-themes（含自定义主题）
    client.set_cookie('theme', 'auto', domain='localhost', path='/')
    r = client.get('/login')
    body = r.get_data(as_text=True)
    check("C4 登录页 data-themes 含 sepia", 'data-themes' in body and 'sepia' in body, '')

    print(f'\n==== 界面主题回归：共 {len(results)} 项，'
          f'通过 {sum(1 for _, c, _ in results if c)}，'
          f'失败 {sum(1 for _, c, _ in results if not c)} ====')
    ok = all(c for _, c, _ in results)
    sys.exit(0 if ok else 1)

if __name__ == '__main__':
    main()
