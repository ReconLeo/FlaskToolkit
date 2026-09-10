# -*- coding: utf-8 -*-
"""设备检测 + 移动端模板分发（v4.17）

服务端按 User-Agent 分发独立移动端模板，脱离 v4.13 "桌面端 + xxx_mobile.css/mobile.js 样式补充"模式。
- 手机端（mobile）渲染独立移动端模板 templates/mobile/<name>；
- 平板（tablet）走桌面端响应式，避免移动端模板在小屏不理想的退化；
- 提供统一分发工具 resolve_template / render，供框架页面、后台与 BasePlugin 复用。

纯 stdlib，无新增运行时依赖。
"""
import logging

import global_var

logger = logging.getLogger('flask.app')


def detect_device(user_agent):
    """按 UA 判定设备类型：返回 'mobile' | 'tablet' | 'desktop'。

    复用 core.stats.classify_device 的字符串匹配逻辑；bot/爬虫视为 desktop（渲染桌面端，不强制移动端）。
    """
    from core.stats import classify_device
    raw = classify_device(user_agent)
    if raw in ('mobile', 'tablet'):
        return raw
    return 'desktop'


def _request_ua():
    """读取当前请求的 User-Agent；无请求上下文（如 CLI/测试直接调用）返回 ''。"""
    try:
        from flask import request
        return request.headers.get('User-Agent', '') or ''
    except Exception:
        return ''


def get_device():
    """当前请求设备类型：'mobile' | 'tablet' | 'desktop'。

    配置 FORCE_MOBILE=True 时强制返回 'mobile'（调试/测试用）。
    """
    if global_var.FORCE_MOBILE:
        return 'mobile'
    return detect_device(_request_ua())


def mobile_enabled():
    """移动端分离开关（MOBILE_ENABLED，默认开）。"""
    return bool(getattr(global_var, 'MOBILE_ENABLED', True))


def is_mobile():
    """当前请求是否为手机端。

    手机端渲染移动端模板；tablet 走桌面端响应式（不视为 mobile）避免退化。
    MOBILE_ENABLED=False 或 FORCE_MOBILE=True 均影响判定。
    """
    if not mobile_enabled():
        return False
    if global_var.FORCE_MOBILE:
        return True
    return get_device() == 'mobile'


def _template_exists(name):
    """判断 Jinja 模板是否存在（try/except get_template，不存在返回 False）。"""
    from flask import current_app
    name = name.replace('\\', '/')
    try:
        current_app.jinja_env.get_template(name)
        return True
    except Exception:
        return False


def resolve_template(template):
    """移动端模板分发核心：返回实际应渲染的模板名。

    手机端且移动端模板 templates/mobile/<template> 存在 → 返回 'mobile/<template>'；
    否则返回原桌面端模板名（安全回退，避免 500）。
    供 render_template 直接使用，也供 BasePlugin 的移动端能力复用。
    """
    template = template.replace('\\', '/')
    if is_mobile():
        mobile_name = 'mobile/' + template
        if _template_exists(mobile_name):
            return mobile_name
    return template


def render(template, **context):
    """统一模板渲染入口：自动做移动端分发（等价 render_template(resolve_template(template))）。

    框架页面 / 后台可改用本入口以自动接入移动端独立模板。
    """
    from flask import render_template
    return render_template(resolve_template(template), **context)
