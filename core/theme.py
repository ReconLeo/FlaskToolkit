# -*- coding: utf-8 -*-
"""FlaskToolkit 界面主题能力（v4.19.0 深色模式，v4.19.2 可扩展主题）。

主题选择（镜像 ``core/i18n.py`` 的语言机制）：
- 优先级：Cookie ``theme`` > 用户配置 ``THEME`` > ``auto``（跟随系统）。
- 内建：``auto``（跟随系统 prefers-color-scheme）/ ``light``（浅色）/ ``dark``（深色）。
- 可扩展（v4.19.2）：扫描 ``global_var.THEMES_DIR``（默认 ``BASE_DIR/themes``）下的
  ``themes/<name>/{theme.json,theme.css}`` 子目录，发现自定义主题；前端 CSS 通过
  ``[data-theme="<name>"]`` 变量集生效，无需改 JS / 后端逻辑。
- 防注入：主题名须匹配 ``^[a-zA-Z0-9_-]+$`` 白名单；``resolve_theme()`` 只放行已发现主题。
- 兜底：自定义主题运行期被删（Cookie/配置仍指向它）时，各解析函数经 ``_is_valid_theme``
  自动回退 ``auto``，且不清除 Cookie（偏好保留，重放回目录自动恢复）。
"""
import json
import os
import re

import global_var

THEME_COOKIE = 'theme'
DEFAULT_THEME = 'auto'
# 内建主题（无独立 theme.css，走框架 static/css/theme.css 语义变量）
BUILTIN_THEMES = ('auto', 'light', 'dark')
# 主题名白名单正则（防路径注入）
_THEME_NAME_RE = re.compile(r'^[a-zA-Z0-9_-]+$')

# available_themes 扫描缓存：{key: 目录/theme.json 最大 mtime, themes: 自定义主题 {code:title}}
_scan_cache = {'key': None, 'themes': None}


def _scan_mtime_key():
    """主题发现缓存键：THEMES_DIR mtime 与各主题 theme.json mtime 的最大值。

    新增/删除主题目录会改变 THEMES_DIR mtime，修改 theme.json 改变其自身 mtime，
    均触发缓存失效；修改 theme.css 不影响主题列表（仅视觉），不触发。
    """
    d = global_var.THEMES_DIR
    if not os.path.isdir(d):
        return 0.0
    mtimes = []
    try:
        mtimes.append(os.stat(d).st_mtime)
    except OSError:
        return 0.0
    try:
        for name in os.listdir(d):
            if not _THEME_NAME_RE.match(name):
                continue
            tj = os.path.join(d, name, 'theme.json')
            if os.path.isfile(tj):
                mtimes.append(os.stat(tj).st_mtime)
    except OSError:
        pass
    return max(mtimes)


def _scan_custom_themes():
    """扫描 THEMES_DIR 下的自定义主题，返回 {code: title}。"""
    custom = {}
    d = global_var.THEMES_DIR
    if not os.path.isdir(d):
        return custom
    try:
        entries = sorted(os.listdir(d))
    except OSError:
        return custom
    for name in entries:
        if not _THEME_NAME_RE.match(name):
            continue  # 忽略非法目录名
        tj = os.path.join(d, name, 'theme.json')
        if not os.path.isfile(tj):
            continue  # 无声明文件的目录不算主题
        title = name
        try:
            with open(tj, encoding='utf-8') as f:
                data = json.load(f)
            if data.get('name') != name:
                continue  # 声明名与目录名不一致，忽略（防歧义）
            title = data.get('title') or name
        except Exception:
            continue  # theme.json 损坏视为无效，跳过
        custom[name] = title
    return custom


def available_themes():
    """返回可用主题映射 {code: title}（内建 + themes/ 扫描的自定义主题）。

    ``code`` 用于 Cookie/配置/切换路由，``title`` 用于 UI 展示。带 mtime 缓存，
    运行期新增/删除主题目录或改动 theme.json 即失效。
    """
    result = {
        'auto': 'auto',
        'light': 'light',
        'dark': 'dark',
    }
    key = _scan_mtime_key()
    if _scan_cache['key'] != key:
        _scan_cache['key'] = key
        _scan_cache['themes'] = _scan_custom_themes()
    custom = _scan_cache['themes'] or {}
    result.update(custom)
    return result


def _is_valid_theme(theme):
    """主题名是否在可用主题表内（内建 + 已扫描自定义）。"""
    return theme in available_themes()


def resolve_theme(candidate):
    """将候选主题名解析为合法主题名；非法返回 auto。

    仅放行可用主题表内的主题名（内建 + themes/ 已发现），防止路径注入 / 未知值。
    自定义主题被删后不在表内 → 回退 auto（兜底）。
    """
    if _is_valid_theme(candidate):
        return candidate
    return DEFAULT_THEME


def get_theme():
    """解析当前请求主题：Cookie ``theme`` > 用户配置 ``THEME`` > DEFAULT_THEME。

    在 Flask 请求上下文内调用；Cookie/配置值须通过白名单校验，无效（如自定义主题被删）
    时回退 DEFAULT_THEME，但**不清除 Cookie**（偏好保留，重放回目录自动恢复）。
    """
    from flask import request, has_request_context
    from global_var import get_user_config
    if has_request_context():
        raw = request.cookies.get(THEME_COOKIE)
        if raw and _is_valid_theme(raw):
            return raw
    cfg = get_user_config()
    cfg_theme = cfg.get('THEME') or DEFAULT_THEME
    if _is_valid_theme(cfg_theme):
        return cfg_theme
    return DEFAULT_THEME


def resolve_effective_theme(candidate=None):
    """解析“实际生效主题”（供后端/模板渲染用）：

    - 有效自定义主题名 → 返回该主题名（声明值，前端据此挂载自定义 CSS）
    - ``light`` → ``light``、``dark`` → ``dark``
    - ``auto`` / 无效（自定义主题被删） → ``auto``（跟随系统，实际深浅色只能由前端
      theme.js 经 ``prefers-color-scheme`` 解析，后端拿不到浏览器偏好）

    参数 ``candidate`` 省略时取 ``get_theme()``（Cookie > 用户配置 > auto）。
    用于插件/后端需要“当前是什么主题/深浅色”做条件渲染时，避免手写白名单分支。
    """
    theme = candidate if candidate is not None else get_theme()
    if _is_valid_theme(theme) and theme != DEFAULT_THEME:
        return theme
    return DEFAULT_THEME  # auto（跟随系统，交前端解析）


def get_theme_css(name):
    """读取自定义主题 CSS 内容（供 /theme-static/<name>/theme.css 路由）。

    - 白名单正则校验，非法名返回 None；
    - 仅对已发现的自定义主题（非内建三色）开放；
    - 文件不存在 / 读取失败返回 None。视为不可信样式，只读、不执行任何代码。
    """
    if not _THEME_NAME_RE.match(name):
        return None
    if name in BUILTIN_THEMES:
        return None
    p = os.path.join(global_var.THEMES_DIR, name, 'theme.css')
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding='utf-8') as f:
            return f.read()
    except OSError:
        return None
