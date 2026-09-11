# -*- coding: utf-8 -*-
"""FlaskToolkit 界面主题能力（v4.19.0 深色模式）。

主题选择（镜像 ``core/i18n.py`` 的语言机制）：
- 优先级：Cookie ``theme`` > 用户配置 ``THEME`` > ``auto``（跟随系统）。
- 可选值：``auto``（跟随系统 prefers-color-scheme）/ ``light``（浅色）/ ``dark``（深色）。
- 可扩展：在 ``available_themes()`` 中新增主题名即可，前端 CSS 通过
  ``[data-theme="<name>"]`` 变量集生效，无需改 JS / 后端逻辑。
- 防注入：``resolve_theme()`` 只放行注册表内的主题名。
"""
THEME_COOKIE = 'theme'
DEFAULT_THEME = 'auto'


def available_themes():
    """返回可用主题映射 {code: name}（code 用于 Cookie/配置，name 用于 UI 展示）。

    目前为内建注册表；未来可扩展为从 ``themes/`` 目录扫描发现。
    """
    return {
        'auto': 'auto',
        'light': 'light',
        'dark': 'dark',
    }


def _is_valid_theme(theme):
    """主题名是否在白名单内。"""
    return theme in available_themes()


def resolve_theme(candidate):
    """将候选主题名解析为合法主题名；非法返回 auto。

    仅放行注册表内的主题名，防止路径注入 / 未知值。
    """
    if _is_valid_theme(candidate):
        return candidate
    return DEFAULT_THEME


def get_theme():
    """解析当前请求主题：Cookie ``theme`` > 用户配置 ``THEME`` > DEFAULT_THEME。

    在 Flask 请求上下文内调用；Cookie 值须通过白名单校验。
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
