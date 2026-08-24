# -*- coding: utf-8 -*-
"""全局请求拦截器：系统级兜底鉴权（管理员/登录路径守卫），插件 API 权限下放给插件装饰器"""
import urllib.parse

from flask import jsonify, redirect, render_template, request

import global_var


def register(app):
    @app.before_request
    def global_auth_interceptor():
        # 白名单路径：精确匹配或前缀匹配
        EXACT_PUBLIC_PATHS = {  # 精确匹配的白名单
            '/',
            '/login',
            '/logout',
            '/favicon.ico'
        }
        PREFIX_PUBLIC_PATHS = [  # 前缀匹配的白名单
            '/api/auth/login',
            '/api/plugins',
            '/static/',
            '/frontend/'
        ]

        # 系统级兜底鉴权（非插件路径）：
        #   - 管理后台 /admin/ /api/admin/ /debug/ /api/reload 必须管理员
        #   - 插件页面 /plugin/ 必须登录
        # 注意：插件 API（/api/<plugin>/...）的权限由插件自身的 @permission / require_role 装饰器决定，此处不做强制。
        ADMIN_GUARD_PREFIXES = ['/admin/', '/api/admin/', '/debug/', '/api/reload']
        LOGIN_GUARD_PREFIXES = ['/plugin/']

        path = request.path

        # 1. 白名单校验：先精确匹配，再前缀匹配
        if path in EXACT_PUBLIC_PATHS:
            return None
        for prefix in PREFIX_PUBLIC_PATHS:
            if path.startswith(prefix):
                return None

        # 2. auth 插件不存在：可选鉴权，全部放行
        if 'auth' not in global_var.plugins:
            return None

        # 3. 判断是否命中系统兜底路径
        need_admin = any(path.startswith(p) for p in ADMIN_GUARD_PREFIXES)
        need_login = any(path.startswith(p) for p in LOGIN_GUARD_PREFIXES)
        if not (need_admin or need_login):
            return None  # 插件 API/页面交由插件装饰器与页面逻辑处理

        # 4. 校验登录态（修复：auth 存在时无论是否携带 token 都必须校验，未登录一律拦截）
        token = request.headers.get('X-Token') or request.cookies.get('token') or request.args.get('token')
        user_info = global_var.plugins['auth'].verify_token(token) if token else None
        if not user_info:
            if path.startswith('/api/'):
                return jsonify({"code": 401, "message": "未登录或登录已过期"}), 401
            redirect_url = urllib.parse.quote_plus(request.full_path)
            return redirect(f'/login?redirect={redirect_url}')

        request.user = user_info

        # 5. 管理员路径权限校验
        if need_admin and user_info.get('role') != 'admin':
            if path.startswith('/api/'):
                return jsonify({"code": 403, "message": "需要管理员权限"}), 403
            return render_template('403.html', message="仅管理员可访问此页面"), 403

        return None
