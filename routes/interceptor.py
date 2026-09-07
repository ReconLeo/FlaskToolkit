# -*- coding: utf-8 -*-
"""全局请求拦截器：系统级兜底鉴权（管理员/登录路径守卫），插件 API 权限下放给插件装饰器"""
import time
import urllib.parse

from flask import jsonify, redirect, render_template, request

import global_var
from core.stats import record_page_view, record_request_stats


def register(app):
    @app.before_request
    def global_auth_interceptor():
        # v4.14 Statistics：记录请求开始时间（after_request 计算延迟）
        request._ft_stats_t0 = time.time()

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
        # /__plugin_api__/ 调试页仅管理员可见（v4.10）：普通用户无需看到 API 文档/调试界面
        ADMIN_GUARD_PREFIXES = ['/admin/', '/api/admin/', '/debug/', '/api/reload', '/__plugin_api__/']
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

        # 3.1 插件公开页面豁免：插件实例声明 public_page=True 时，其 /plugin/ 页面无需登录。
        #     对局域网公开工具 / 信息落地页友好（如 AirDrop 免登录模式）。
        #     默认 False，不影响其他插件的页面登录守卫。
        if need_login and path.startswith('/plugin/'):
            _parts = path.split('/')
            if len(_parts) >= 3:
                _plugin = global_var.plugins.get(_parts[2])
                if _plugin is not None and getattr(_plugin, 'public_page', False):
                    return None

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

    @app.after_request
    def global_stats_recorder(response):
        """v4.14 Statistics：请求后聚合——插件 API / 前端工具写时间桶+画像，插件页面仅画像。
        累计计数（call_stats / frontend_access_stats）由原埋点维护，此处职责分离不重复计数。"""
        try:
            ctx = getattr(request, '_ft_stats_t0', None)
            path = request.path
            ms = (time.time() - ctx) * 1000 if ctx else -1
            ua = request.headers.get('User-Agent', '')
            ip = request.remote_addr or ''
            user = getattr(request, 'user', None)
            username = user.get('username') if isinstance(user, dict) else None
            status = response.status_code

            # 插件 API（排除后台自身 /api/admin/）：/api/<plugin>/<rest>
            if path.startswith('/api/') and not path.startswith('/api/admin/'):
                parts = path.split('/')
                if len(parts) >= 3 and parts[2]:
                    plugin = parts[2]
                    endpoint = '/' + '/'.join(parts[3:]) if len(parts) > 3 else ''
                    record_request_stats(plugin, endpoint or '/', status, ms,
                                         username, ip, ua, frontend=False)
            # 前端工具页面：/frontend/<tool>
            elif path.startswith('/frontend/'):
                parts = path.split('/')
                tool = parts[2] if len(parts) >= 3 else ''
                if tool:
                    record_request_stats(None, tool, status, ms,
                                         username, ip, ua, frontend=True)
            # 插件页面访问：仅画像（登录守卫/公开页豁免后的页面浏览）
            elif path.startswith('/plugin/') and not path.startswith('/plugin/static'):
                parts = path.split('/')
                if len(parts) >= 3 and parts[2]:
                    record_page_view(username, ip, ua)
        except Exception as e:
            # 统计失败不影响业务响应
            app.logger.warning(f"统计记录异常: {str(e)}", extra={'plugin': 'system'})
        return response
