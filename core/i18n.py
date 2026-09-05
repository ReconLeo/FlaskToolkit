# -*- coding: utf-8 -*-
"""core/i18n.py — v4.9.0 轻量可扩展语言框架（零第三方依赖）

设计要点：
- 语言包：``locales/<lang>.json`` 键值对；**中文原文即 key**（如 {"登录": "Login"}），
  迁移成本低、无需维护语义 key 表；改文案时同步语言包（测试固化）。
- 查找链：插件语言包（plugins/<name>/locales/<lang>.json，可覆盖框架词条）
  → 框架语言包（locales/<lang>.json）→ key 原文（缺省回退）。
- 语言选择：Cookie ``lang`` > 用户配置 ``LANGUAGE`` > DEFAULT_LANG（zh-CN）。
- ``t(key, **params)``：缺省回退返回原文；支持 ``{placeholder}`` 参数插值。
- 扩展语言 = 在 locales/ 新增 ``<lang>.json`` 即可，自动被发现。
- 安全：语言代码白名单校验（仅允许 locales/ 下真实存在的语言包），防止路径注入。
"""
import json
import os
import threading

from global_var import BASE_DIR

DEFAULT_LANG = 'zh-CN'
LANG_COOKIE = 'lang'

# 线程局部：当前请求的翻译器（t 函数读取它）
_local = threading.local()

# 语言包缓存：lang -> dict（插件词条合并后的完整表）；TTL 缓存避免每次请求扫描磁盘
_cache = {}          # lang -> translations
_cache_mtime = {}    # lang -> (框架语言包 mtime, 插件目录扫描指纹)

# 插件语言包目录指纹缓存
_plugin_fp = None    # plugins/locales 存在性指纹


def _plugin_locales_fingerprint():
    """插件目录中 locales/ 的存在性指纹（用于缓存失效判断）。"""
    plugins_dir = os.path.join(BASE_DIR, 'plugins')
    names = []
    try:
        for n in sorted(os.listdir(plugins_dir)):
            ldir = os.path.join(plugins_dir, n, 'locales')
            if os.path.isdir(ldir):
                names.append(n)
    except OSError:
        return ()
    return tuple(names)


def available_languages():
    """扫描 locales/ 返回可用语言映射 {code: name}（如 {'zh-CN': '简体中文', 'en': 'English'})。

    语言自称取自语言包内 ``__name__`` 字段；未声明时回退为语言代码。
    """
    base = os.path.join(BASE_DIR, 'locales')
    result = {}
    if os.path.isdir(base):
        for f in sorted(os.listdir(base)):
            if f.endswith('.json'):
                code = f[:-5]
                name = code
                try:
                    with open(os.path.join(base, f), encoding='utf-8') as fp:
                        d = json.load(fp)
                    if isinstance(d, dict) and isinstance(d.get('__name__'), str) and d['__name__']:
                        name = d['__name__']
                except (OSError, ValueError):
                    pass
                result[code] = name
    return result


def _is_valid_lang(lang):
    """语言代码白名单校验：必须对应 locales/ 下真实存在的语言包。"""
    return lang in available_languages()


def _load_framework(lang):
    """加载框架语言包（locales/<lang>.json）。"""
    p = os.path.join(BASE_DIR, 'locales', lang + '.json')
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _load_plugin_merges(lang):
    """合并所有插件的 locales/<lang>.json（插件词条覆盖框架词条）。

    仅当插件目录中实际存在 locales/ 时才逐个加载；缓存由调用方按指纹失效。
    """
    merged = {}
    plugins_dir = os.path.join(BASE_DIR, 'plugins')
    try:
        for n in sorted(os.listdir(plugins_dir)):
            p = os.path.join(plugins_dir, n, 'locales', lang + '.json')
            if os.path.isfile(p):
                try:
                    with open(p, encoding='utf-8') as f:
                        d = json.load(f)
                    if isinstance(d, dict):
                        merged.update(d)
                except (OSError, ValueError):
                    continue
    except OSError:
        pass
    return merged


def _build_translations(lang):
    """构建 lang 的完整翻译表（框架 + 插件合并），带缓存。"""
    global _plugin_fp
    fp = _plugin_locales_fingerprint()
    if _plugin_fp != fp:
        _cache.clear()          # 插件目录结构变化 → 全量失效
        _cache_mtime.clear()
        _plugin_fp = fp
    if lang in _cache:
        return _cache[lang]
    table = _load_framework(lang)
    table.update(_load_plugin_merges(lang))
    _cache[lang] = table
    return table


def make_translator(lang):
    """为指定语言创建翻译器（t 函数闭包）。"""
    table = _build_translations(lang)

    def t(key, **params):
        text = table.get(key, key)          # 缺省回退返回原文
        if params:
            try:
                text = text.format(**params)
            except (KeyError, ValueError, IndexError):
                pass                         # 占位符不匹配时返回未插值文本
        return text

    t.table = table                 # 暴露翻译表（供前端 window.T 注入）
    return t


def get_translator():
    """获取当前线程/请求的翻译器（后端代码调用）。"""
    tr = getattr(_local, 'translator', None)
    if tr is None:
        tr = make_translator(DEFAULT_LANG)
    return tr


def set_current_translator(tr):
    """设置当前线程/请求的翻译器（由 app 上下文处理器调用）。"""
    _local.translator = tr


def get_lang():
    """解析当前请求语言：Cookie ``lang`` > 用户配置 ``LANGUAGE`` > DEFAULT_LANG。

    在 Flask 请求上下文内调用；Cookie 值须通过白名单校验。
    """
    from flask import request, has_request_context
    from global_var import get_user_config
    # Cookie 优先（无请求上下文时跳过——插件在测试/后台线程直接 render 的场景）
    if has_request_context():
        raw = request.cookies.get(LANG_COOKIE)
        if raw and _is_valid_lang(raw):
            return raw
    # 用户配置次之
    cfg = get_user_config()
    cfg_lang = cfg.get('LANGUAGE') or DEFAULT_LANG
    if _is_valid_lang(cfg_lang):
        return cfg_lang
    return DEFAULT_LANG


def resolve_lang(candidate):
    """外部候选语言代码 → 合法语言（无效回退默认）。"""
    if candidate and _is_valid_lang(candidate):
        return candidate
    return DEFAULT_LANG
