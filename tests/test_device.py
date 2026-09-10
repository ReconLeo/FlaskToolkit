# -*- coding: utf-8 -*-
"""v4.17 设备检测 + 移动端模板分发回归（core/device.py + 公开页/BasePlugin 移动端独立渲染）

覆盖：
- detect_device UA 分类（mobile/tablet/desktop，bot 视为 desktop）
- is_mobile / mobile_enabled 配置开关（MOBILE_ENABLED / FORCE_MOBILE）
- resolve_template 移动端模板存在性分发（存在 mobile/<name> 用移动端，否则回退桌面）
- 公开页（/login）移动端 UA 渲染移动端模板、桌面端 UA 渲染桌面模板
- BasePlugin.render 移动端命名空间 plugins/<name>/mobile/<t> 分发

运行：python test_device.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import global_var

_PASS = 0
_FAIL = 0


def check(name, cond, detail=''):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  ✓ {name}")
    else:
        _FAIL += 1
        print(f"  ✗ {name}  {detail}")


# ---------- 1. core/device 纯函数 ----------
from core import device

MOBILE_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148'
TABLET_UA = 'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15'
DESKTOP_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36'
BOT_UA = 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
ANDROID_UA = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 Mobile Safari/537.36'

check("detect: iPhone → mobile", device.detect_device(MOBILE_UA) == 'mobile')
check("detect: Android → mobile", device.detect_device(ANDROID_UA) == 'mobile')
check("detect: iPad → tablet（不视为 mobile）", device.detect_device(TABLET_UA) == 'tablet')
check("detect: Windows → desktop", device.detect_device(DESKTOP_UA) == 'desktop')
check("detect: bot → desktop（不强制移动端）", device.detect_device(BOT_UA) == 'desktop')
check("detect: 空 UA → desktop", device.detect_device('') == 'desktop')

check("mobile_enabled 默认开", device.mobile_enabled() is True)

# ---------- 2. resolve_template：用真实模板环境（登录/首页） ----------
import app as appmod
app = appmod.app
app.config['TESTING'] = True
client = app.test_client()

r = client.get('/login', headers={'User-Agent': MOBILE_UA})
check("登录页 移动端 UA → 渲染移动端模板（含 mobile-app.css）",
      b'mobile-app.css' in r.data, f'status={r.status_code}')
check("登录页 移动端 UA 含 'body class=mobile'", b'class="mobile"' in r.data)

r = client.get('/login', headers={'User-Agent': DESKTOP_UA})
check("登录页 桌面端 UA → 渲染桌面模板（不含 mobile-app.css）",
      b'mobile-app.css' not in r.data, f'status={r.status_code}')

r = client.get('/login', headers={'User-Agent': TABLET_UA})
check("登录页 平板 UA → 桌面端响应式（不含 mobile-app.css）",
      b'mobile-app.css' not in r.data, f'status={r.status_code}')

# ---------- 3. FORCE_MOBILE 强制手机端 ----------
_saved_fm = global_var.FORCE_MOBILE
global_var.FORCE_MOBILE = True
try:
    r = client.get('/login', headers={'User-Agent': DESKTOP_UA})
    check("FORCE_MOBILE=True 桌面 UA 也渲染移动端模板",
          b'mobile-app.css' in r.data, f'status={r.status_code}')
finally:
    global_var.FORCE_MOBILE = _saved_fm

# ---------- 4. MOBILE_ENABLED 关闭时全部回退桌面 ----------
_saved_me = global_var.MOBILE_ENABLED
global_var.MOBILE_ENABLED = False
try:
    r = client.get('/login', headers={'User-Agent': MOBILE_UA})
    check("MOBILE_ENABLED=False 移动端 UA 回退桌面模板",
          b'mobile-app.css' not in r.data, f'status={r.status_code}')
finally:
    global_var.MOBILE_ENABLED = _saved_me

# ---------- 5. resolve_template 模板存在性 ----------
from flask import render_template
# 登录页移动端模板存在 → resolve 返回 mobile/login.html
with app.test_request_context(headers={'User-Agent': MOBILE_UA}):
    resolved = device.resolve_template('login.html')
    check("resolve_template('login.html') 移动端 → mobile/login.html", resolved == 'mobile/login.html', resolved)
with app.test_request_context(headers={'User-Agent': DESKTOP_UA}):
    resolved = device.resolve_template('login.html')
    check("resolve_template('login.html') 桌面端 → login.html", resolved == 'login.html', resolved)
    # 不存在的移动端模板安全回退
    resolved = device.resolve_template('404.html')
    check("resolve_template('404.html') 桌面端 → 404.html", resolved == '404.html', resolved)


# ---------- 6. BasePlugin 移动端命名空间分发 ----------
def test_baseplugin_mobile():
    """构造一个带移动端模板的插件，验证 render() 移动端渲染 mobile/ 命名空间。

    用 DictLoader 注入模板（不写文件，避免安全策略拦截删除 + 不污染工作区）。
    """
    from plugins.base_plugin import BasePlugin
    from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader

    class _P(BasePlugin):
        name = 'device_tpl'
        title = 'Device Tpl'
        version = '1.0.0'
        description = 'test'
        permission = 'public'
        category = '测试'

        def routes(self):
            return []

    # 用 DictLoader 在内存中提供插件桌面/移动端模板，注入 app 的 Jinja loader
    extra_loader = DictLoader({
        'plugins/device_tpl/page.html': '<html><body>DESKTOP_PAGE</body></html>',
        'plugins/device_tpl/mobile/page.html': '<html><body>MOBILE_PAGE</body></html>',
    })
    old_loader = app.jinja_env.loader
    app.jinja_env.loader = ChoiceLoader([old_loader, extra_loader])
    try:
        p = _P()
        p.enabled = True
        # 桌面端
        with app.test_request_context(headers={'User-Agent': DESKTOP_UA}):
            resp = p.render('page.html')
            check("BasePlugin.render 桌面端 → 桌面模板", b'DESKTOP_PAGE' in resp.data, resp.data[:80])
        # 移动端
        with app.test_request_context(headers={'User-Agent': MOBILE_UA}):
            resp = p.render('page.html')
            check("BasePlugin.render 移动端 → mobile/ 移动端模板", b'MOBILE_PAGE' in resp.data, resp.data[:80])
            check("is_mobile_context() 移动端为 True", p.is_mobile_context() is True)
        with app.test_request_context(headers={'User-Agent': TABLET_UA}):
            check("is_mobile_context() 平板为 False（走桌面响应式）", p.is_mobile_context() is False)
    finally:
        # 恢复原 loader 并清缓存
        app.jinja_env.loader = old_loader
        try:
            app.jinja_env.cache.clear()
        except Exception:
            pass


test_baseplugin_mobile()

print(f"\n==== 结果：{_PASS} 通过, {_FAIL} 失败 ====")
sys.exit(1 if _FAIL else 0)
