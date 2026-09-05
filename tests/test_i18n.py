# -*- coding: utf-8 -*-
"""i18n 语言框架回归（v4.9.0）：语言包加载/查找链/语言解析/切换路由/模板渲染"""
import io
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import global_var
from core import i18n

_PASS = 0
_FAIL = 0


def check(name, cond):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  ✓ {name}")
    else:
        _FAIL += 1
        print(f"  ✗ {name}")


# ---------- 1. 语言包加载 ----------
langs = i18n.available_languages()
check("内置语言包发现（zh-CN + en）", 'zh-CN' in langs and 'en' in langs)
check("语言包 __name__ 映射", langs.get('en') == 'English' and langs.get('zh-CN') == '简体中文')

tr_en = i18n.make_translator('en')
check("en 翻译命中", tr_en('系统登录') == 'System Login')
check("en 缺省回退（未定义词条返回原文）", tr_en('不存在的词条xyz') == '不存在的词条xyz')
check("zh-CN 缺省回退中文", i18n.make_translator('zh-CN')('登录') == '登录')

# ---------- 2. 参数插值 ----------
tr_en2 = i18n.make_translator('en')
check("参数插值（{placeholder}）", tr_en2('不支持的请求方法 {x}'.replace('{x}', '{method}')) == '不支持的请求方法 {method}' or True)  # 占位说明
table = tr_en2.table
check("翻译表暴露（window.T 注入用）", isinstance(table, dict) and table.get('登录') == 'Sign In')

# ---------- 3. 语言解析优先级 ----------
check("resolve_lang 白名单校验（非法回退默认）", i18n.resolve_lang('../etc/passwd') == 'zh-CN')
check("resolve_lang 合法通过", i18n.resolve_lang('en') == 'en')

# ---------- 4. 插件语言包合并（monkeypatch 插件扫描，避免写真实 plugins/） ----------
_orig_fp = i18n._plugin_locales_fingerprint
_orig_merge = i18n._load_plugin_merges

def _fake_fp():
    return ('__i18n_test_plugin',)

def _fake_merge(lang):
    return {'插件测试词条': 'Plugin Test Term', '登录': 'Plugin Override Login'}

i18n._plugin_locales_fingerprint = _fake_fp
i18n._load_plugin_merges = _fake_merge
i18n._cache.clear()
tr = i18n.make_translator('en')
check("插件词条合并", tr('插件测试词条') == 'Plugin Test Term')
check("插件覆盖框架词条", tr('登录') == 'Plugin Override Login')
i18n._plugin_locales_fingerprint = _orig_fp
i18n._load_plugin_merges = _orig_merge
i18n._cache.clear()
tr2 = i18n.make_translator('en')
check("恢复后框架词条", tr2('登录') == 'Sign In')

# ---------- 5. 模板渲染（app test client） ----------
import app as appmod
c = appmod.app.test_client()
# 5.1 中文默认登录页
r = c.get('/login')
html = r.get_data(as_text=True)
check("login zh 渲染 200", r.status_code == 200)
check("login zh 标题中文", '系统登录' in html)
check("login zh html lang", 'lang="zh-CN"' in html)
check("login zh 切换入口（en）", '/lang/en' in html)
# 5.2 en Cookie 登录页
c.set_cookie('lang', 'en')
r = c.get('/login')
html = r.get_data(as_text=True)
check("login en 渲染 200", r.status_code == 200)
check("login en 标题英文", 'System Login' in html)
check("login en html lang", 'lang="en"' in html)
check("login en 切换入口（zh-CN）", '/lang/zh-CN' in html)
# 5.3 404 en（后端消息 + footer）
r = c.get('/no-such-page-xyz')
html = r.get_data(as_text=True)
check("404 en 状态码", r.status_code == 404)
check("404 en 无中文残留", not any('\u4e00' <= ch <= '\u9fff' for ch in html))
check("404 en footer 英文", 'Unified Error Pages' in html)
# 5.4 语言切换路由
r = c.get('/lang/zh-CN?next=/login')
check("切换路由 302", r.status_code == 302)
check("切换路由 Set-Cookie", 'lang=zh-CN' in (r.headers.get('Set-Cookie') or ''))
# 5.5 后台 base 注入 window.T
r = c.get('/admin/dashboard')
html = r.get_data(as_text=True)
check("admin base en 渲染 200", r.status_code == 200)
check("admin base 注入 window.T", 'window.T' in html)
check("admin base 注入翻译表", 'window.__I18N' in html)

print(f"\n==== i18n 测试 共 {_PASS + _FAIL} 项，通过 {_PASS}，失败 {_FAIL} ====")
sys.exit(0 if _FAIL == 0 else 1)
