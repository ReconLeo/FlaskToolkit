# -*- coding: utf-8 -*-
"""公开路由：首页、登录/登出、403 页、favicon、错误处理器（游客可访问）"""
import logging
import os
import time
import urllib.parse

from flask import jsonify, make_response, redirect, render_template, request, send_from_directory
from core import device

import global_var
from core import i18n

def _tr():
    """当前请求语言的翻译器（错误消息用）。"""
    return i18n.make_translator(i18n.get_lang())


def _setup_done_file() -> str:
    '''首次运行向导完成标记（v4.10）：data/.setup_done，存在即视为已初始化。'''
    return os.path.join(global_var.BASE_DIR, 'data', '.setup_done')


def _is_setup_done() -> bool:
    return os.path.exists(_setup_done_file())

logger = logging.getLogger('flask.app')


def register(app):
    @app.route('/setup', methods=['GET', 'POST'])
    def setup_page():
        '''v4.10 首次运行向导：未完成初始化时访问首页跳转至此。'''
        done_file = _setup_done_file()
        if request.method == 'POST':
            lang = (request.form.get('lang') or '').strip()
            # v4.20.3：动态白名单——接受所有可用语言（locales/ 下真实存在的语言包，含扩展语言如 fr），
            # 不再硬编码 zh-CN/en，否则 setup 下拉可选 fr 但提交不生效
            if lang in i18n.available_languages():
                try:
                    import json as _json
                    cfg_file = global_var.USER_CONFIG_FILE
                    data = {}
                    if os.path.isfile(cfg_file):
                        with open(cfg_file, encoding='utf-8') as _f:
                            data = _json.load(_f)
                    if not isinstance(data, dict):
                        data = {}
                    data['LANGUAGE'] = lang
                    with open(cfg_file, 'w', encoding='utf-8') as _f:
                        _json.dump(data, _f, ensure_ascii=False, indent=2)
                    from global_var import load_user_config
                    load_user_config()
                except Exception:
                    pass
            try:
                os.makedirs(os.path.dirname(done_file), exist_ok=True)
                with open(done_file, 'w', encoding='utf-8') as _f:
                    _f.write(time.strftime('%Y-%m-%d %H:%M:%S'))
            except Exception:
                pass
            return redirect('/')
        if os.path.exists(done_file):
            return redirect('/')
        # 双语并显：分别取简中/英文翻译器，以当前主语言高亮（默认简中为主、英文为次）
        primary = i18n.get_lang() if i18n.get_lang() in ('zh-CN', 'en') else 'zh-CN'
        secondary = 'en' if primary == 'zh-CN' else 'zh-CN'
        return render_template(
            'setup.html',
            FRAMEWORK_VERSION=global_var.FRAMEWORK_VERSION,
            zh_t=i18n.make_translator('zh-CN'),
            en_t=i18n.make_translator('en'),
            primary_lang=primary,
            secondary_lang=secondary,
            available_langs=i18n.available_languages(),
        )
    @app.route('/login')
    def login_page():
        """全局登录页面"""
        # 已登录用户直接跳转到首页或来源页
        token = request.cookies.get('token') or request.args.get('token')
        if token and 'auth' in global_var.plugins and global_var.plugins['auth'].verify_token(token):
            redirect_url = request.args.get('redirect', '/')
            return redirect(urllib.parse.unquote_plus(redirect_url))
        # v4.10 M5：注册开关（auth 插件 config）传前端控制"注册账号"入口显示
        allow_register = False
        if 'auth' in global_var.plugins:
            _auth_cfg = getattr(global_var.plugins['auth'], 'config', None) or {}
            allow_register = bool(_auth_cfg.get('ALLOW_REGISTER', False))
        return device.render('login.html', allow_register=allow_register)

    @app.route('/register')
    def register_page():
        """v4.10 M5 自助注册页：邀请码经 URL params 自动填充（/register?code=xxx）"""
        invite_code = request.args.get('code', '')
        return render_template('register.html', invite_code=invite_code)

    @app.route('/lang/<code>')
    def switch_lang(code):
        """切换显示语言（v4.9.0）：GET /lang/<code>?next=<redirect>，设置 lang Cookie 后跳转。

        语言代码须通过白名单校验（locales/ 下真实存在的语言包），防止路径注入。
        """
        from core import i18n
        target = i18n.resolve_lang(code)
        next_url = request.args.get('next', '/')
        # 仅允许站内相对路径重定向，防开放重定向
        if next_url.startswith('//') or '://' in next_url:
            next_url = '/'
        response = make_response(redirect(next_url))
        response.set_cookie(i18n.LANG_COOKIE, target, max_age=31536000, samesite='Lax')
        return response

    @app.route('/theme/<code>')
    def switch_theme(code):
        """切换界面主题（v4.19.0）：GET /theme/<code>?next=<redirect>，设置 theme Cookie 后跳转。

        主题名须通过白名单校验（core.theme 注册表），防止路径注入。
        """
        from core import theme
        target = theme.resolve_theme(code)
        next_url = request.args.get('next', '/')
        # 仅允许站内相对路径重定向，防开放重定向
        if next_url.startswith('//') or '://' in next_url:
            next_url = '/'
        response = make_response(redirect(next_url))
        response.set_cookie(theme.THEME_COOKIE, target, max_age=31536000, samesite='Lax')
        return response

    @app.route('/theme-static/<name>/theme.css')
    def theme_static_css(name):
        """自定义主题 CSS（v4.19.2）：GET /theme-static/<name>/theme.css。

        供前端 theme.js 为自定义主题按需挂载样式；主题名白名单正则校验，
        CSS 视为不可信样式只读返回，不存在返回 404。
        """
        from core import theme
        css = theme.get_theme_css(name)
        if css is None:
            return '', 404
        response = make_response(css)
        response.headers['Content-Type'] = 'text/css; charset=utf-8'
        response.headers['Cache-Control'] = 'public, max-age=300'
        return response

    @app.route('/user-center')
    def user_center():
        """用户中心（v4.20）：登录用户自助修改昵称/密码（用户名不可改）。

        页面本身经 interceptor LOGIN_GUARD_PREFIXES 守卫，未登录自动重定向 /login；
        当前用户信息由页面 JS 经 /api/auth/user/info 获取并填充。
        """
        return render_template('user_center.html')

    @app.route('/logout')
    def logout_page():
        """全局登出页面"""
        # 清除登录状态后跳转到登录页
        response = make_response(render_template('logout.html'))
        # cookie重置由鉴权插件处理
        return response

    @app.route('/')
    def index():
        # v4.10 首次运行向导：未完成初始化时跳转 /setup
        if not _is_setup_done():
            return redirect('/setup')
        logger.info("访问首页", extra={'plugin': 'system'})
        # 合并后端插件（内存注册表 plugin_catalog，含禁用/未加载项）和前端工具
        all_tools = [dict(t) for t in global_var.plugin_catalog]
        all_tools.extend(global_var.frontend_tools)

        # 热度：后端插件=该插件全部 API 调用数之和；前端工具=访问数（供首页搜索/排序）
        heat_map = {}
        for key, count in global_var.call_stats.items():
            plugin_name = key.split(':', 1)[0]
            heat_map[plugin_name] = heat_map.get(plugin_name, 0) + count
        for key, count in global_var.frontend_access_stats.items():
            tool_name = key.split(':', 1)[1] if ':' in key else key
            heat_map[tool_name] = heat_map.get(tool_name, 0) + count
        for tool in all_tools:
            tool['_heat'] = heat_map.get(tool.get('name'), 0)

        # 获取当前登录用户角色（auth插件不存在时默认拥有所有权限）
        user_role = None
        if 'auth' in global_var.plugins:
            token = request.cookies.get('token') or request.headers.get('X-Token') or request.args.get('token')
            if token:
                user_info = global_var.plugins['auth'].verify_token(token)
                if user_info:
                    user_role = user_info.get('role', 'user')

        # 按分类分组+权限过滤
        categories = {}
        for tool in all_tools:
            # 只添加已启用的工具
            if not tool.get('enabled', True):
                continue

            # 权限校验：
            # 1. auth插件不存在：所有工具都可见
            # 2. 未登录：只可见permission为user的工具
            # 3. 已登录普通用户：只可见permission为user的工具
            # 4. 已登录管理员：所有工具都可见
            required_perm = tool.get('permission', 'user')
            if 'auth' in global_var.plugins:
                if user_role != 'admin' and required_perm == 'admin':
                    continue  # 非管理员用户过滤掉需要admin权限的工具

            category = tool['category']
            if category not in categories:
                categories[category] = []
            categories[category].append(tool)

        # 过滤掉空分类
        categories = {k: v for k, v in categories.items() if v}

        # 将当前用户角色传到前端，用于页面动态渲染（v4.17：移动端分发独立模板）
        return device.render(
            'index.html',
            FRAMEWORK_VERSION=global_var.FRAMEWORK_VERSION,
            categories=categories,
            user_role=user_role  # 未登录/无auth插件时为None
        )

    # /403 页面路由（前端权限不足跳转目标）
    @app.route('/403')
    def forbidden_page():
        return render_template('403.html', message=request.args.get('message', _tr()('您没有权限访问该资源'))), 403

    # 400错误处理器
    @app.errorhandler(400)
    def bad_request_error(e):
        logger.warning(f"400请求错误: {request.path} - {str(e)}", extra={'plugin': 'system'})
        return render_template('400.html', message=_tr()("请求参数有误或格式不正确")), 400

    # 401错误处理器（页面场景兜底；API 场景由权限模块返回 JSON）
    @app.errorhandler(401)
    def unauthorized_error(e):
        logger.warning(f"401未登录: {request.path} - IP: {request.remote_addr}", extra={'plugin': 'system'})
        return render_template('401.html', message=_tr()("未登录或登录已过期，请重新登录")), 401

    # 403错误处理器
    @app.errorhandler(403)
    def forbidden_error(e):
        logger.warning(f"403访问拒绝: {request.path} - IP: {request.remote_addr}", extra={'plugin': 'system'})
        return render_template('403.html', message=_tr()("您没有权限访问该资源")), 403

    # 405错误处理器
    @app.errorhandler(405)
    def method_not_allowed_error(e):
        logger.warning(f"405请求方法不允许: {request.path} - {request.method}", extra={'plugin': 'system'})
        return render_template('405.html', message=f"{_tr()('不支持的请求方法')} {request.method}"), 405

    # 404错误处理器（优化Chrome开发者工具请求过滤）
    @app.errorhandler(404)
    def not_found_error(e):
        # 过滤掉Chrome开发者工具自动请求的路径，避免冗余日志
        ignored_paths = [
            '/.well-known/appspecific/com.chrome.devtools.json',
            '/favicon.ico'
        ]
        if request.path not in ignored_paths:
            logger.warning(f"404访问: {request.path} - IP: {request.remote_addr}", extra={'plugin': 'system'})
        return render_template('404.html', message=_tr()("页面不存在")), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        logger.error(f"500错误: {request.path} - {str(e)}", extra={'plugin': 'system'})
        return render_template('500.html', message=_tr()("服务器内部错误")), 500

    # 413 请求体过大处理器（全局 MAX_CONTENT_LENGTH 兜底；API 场景返回 JSON，页面场景渲染模板）
    @app.errorhandler(413)
    def request_entity_too_large(e):
        limit_mb = global_var.MAX_UPLOAD_SIZE_MB
        logger.warning(f"413请求体过大: {request.path} - 限制 {limit_mb}MB", extra={'plugin': 'system'})
        msg = f"{_tr()('请求体超过大小限制')}（{limit_mb}MB）"
        if request.path.startswith('/api/'):
            return jsonify({"code": 413, "message": msg}), 413
        return render_template('413.html', message=msg), 413

    # favicon.ico路由处理
    @app.route('/favicon.ico')
    def favicon():
        return send_from_directory(
            os.path.join(app.root_path, 'static'),
            'favicon.ico',
            mimetype='image/vnd.microsoft.icon'
        )
