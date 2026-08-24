# -*- coding: utf-8 -*-
"""公开路由：首页、登录/登出、403 页、favicon、错误处理器（游客可访问）"""
import logging
import os
import urllib.parse

from flask import jsonify, make_response, redirect, render_template, request, send_from_directory

import global_var

logger = logging.getLogger('flask.app')


def register(app):
    @app.route('/login')
    def login_page():
        """全局登录页面"""
        # 已登录用户直接跳转到首页或来源页
        token = request.cookies.get('token') or request.args.get('token')
        if token and 'auth' in global_var.plugins and global_var.plugins['auth'].verify_token(token):
            redirect_url = request.args.get('redirect', '/')
            return redirect(urllib.parse.unquote_plus(redirect_url))
        return render_template('login.html')

    @app.route('/logout')
    def logout_page():
        """全局登出页面"""
        # 清除登录状态后跳转到登录页
        response = make_response(render_template('logout.html'))
        # cookie重置由鉴权插件处理
        return response

    @app.route('/')
    def index():
        logger.info("访问首页", extra={'plugin': 'system'})
        # 合并后端插件（内存注册表 plugin_catalog，含禁用/未加载项）和前端工具
        all_tools = [dict(t) for t in global_var.plugin_catalog]
        all_tools.extend(global_var.frontend_tools)

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

        # 将当前用户角色传到前端，用于页面动态渲染
        return render_template(
            'index.html',
            FRAMEWORK_VERSION=global_var.FRAMEWORK_VERSION,
            categories=categories,
            user_role=user_role  # 未登录/无auth插件时为None
        )

    # /403 页面路由（前端权限不足跳转目标）
    @app.route('/403')
    def forbidden_page():
        return render_template('403.html', message=request.args.get('message', '您没有权限访问该资源')), 403

    # 400错误处理器
    @app.errorhandler(400)
    def bad_request_error(e):
        logger.warning(f"400请求错误: {request.path} - {str(e)}", extra={'plugin': 'system'})
        return render_template('400.html', message="请求参数有误或格式不正确"), 400

    # 401错误处理器（页面场景兜底；API 场景由权限模块返回 JSON）
    @app.errorhandler(401)
    def unauthorized_error(e):
        logger.warning(f"401未登录: {request.path} - IP: {request.remote_addr}", extra={'plugin': 'system'})
        return render_template('401.html', message="未登录或登录已过期，请重新登录"), 401

    # 403错误处理器
    @app.errorhandler(403)
    def forbidden_error(e):
        logger.warning(f"403访问拒绝: {request.path} - IP: {request.remote_addr}", extra={'plugin': 'system'})
        return render_template('403.html', message="您没有权限访问该资源"), 403

    # 405错误处理器
    @app.errorhandler(405)
    def method_not_allowed_error(e):
        logger.warning(f"405请求方法不允许: {request.path} - {request.method}", extra={'plugin': 'system'})
        return render_template('405.html', message=f"不支持的请求方法 {request.method}"), 405

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
        return render_template('404.html', message="页面不存在"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        logger.error(f"500错误: {request.path} - {str(e)}", extra={'plugin': 'system'})
        return render_template('500.html', message="服务器内部错误"), 500

    # favicon.ico路由处理
    @app.route('/favicon.ico')
    def favicon():
        return send_from_directory(
            os.path.join(app.root_path, 'static'),
            'favicon.ico',
            mimetype='image/vnd.microsoft.icon'
        )
