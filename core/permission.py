# -*- coding: utf-8 -*-
"""
统一权限体系：@permission 标记解析 + 三层权限校验（游客/登录/管理员）+ CSRF 双提交

- 插件视图通过 @permission("public"/"user"/"admin") 声明权限，本模块负责解析与落地校验。
- 共享状态一律通过 global_var 引用（保持同一对象，避免与 app.py 显式导入的引用脱钩）。
- 日志使用 logging.getLogger('flask.app')（Flask 默认 logger，与 app.logger 同一实例）。
"""
import logging
import traceback
import urllib.parse
from functools import wraps

from flask import jsonify, redirect, render_template, request, g as flask_g
from werkzeug.exceptions import RequestEntityTooLarge

import global_var
from core.stats import increment_call_stats

logger = logging.getLogger('flask.app')


def wrap_frontend_tool_view(tool_name):
    """前端工具页面访问统计包装器"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            # 统计前端工具访问量
            access_key = f"frontend:{tool_name}"
            global_var.frontend_access_stats[access_key] = global_var.frontend_access_stats.get(access_key, 0) + 1

            logger.info(f"访问前端工具: {tool_name}", extra={'plugin': 'system'})
            return view_func(*args, **kwargs)
        return wrapper
    return decorator


def _resolve_permission(func):
    """沿 __wrapped__ 链解析视图函数的权限标记，未标记返回 None"""
    seen = set()
    while func is not None and id(func) not in seen:
        seen.add(id(func))
        perm = getattr(func, '_permission', None)
        if perm is not None:
            return perm
        func = getattr(func, '__wrapped__', None)
    return None


def _check_permission(permission_level: str):
    """
    统一权限校验（游客/登录/管理员三层）。
    - permission_level == "public": 游客可访问，直接放行
    - auth 插件不存在：可选鉴权模式，全部放行
    - 否则按 user/admin 校验登录态与角色
    返回非 None 表示拦截响应，None 表示放行。
    """
    if permission_level == "public":
        return None

    if "auth" not in global_var.plugins:
        return None

    token = (request.headers.get("X-Token")
             or request.cookies.get("token")
             or request.args.get("token"))
    user_info = global_var.plugins["auth"].verify_token(token)
    if not user_info:
        if request.path.startswith('/api/'):
            return jsonify({"code": 401, "message": "未登录或登录已过期"}), 401
        redirect_url = urllib.parse.quote_plus(request.full_path)
        return redirect(f'/login?redirect={redirect_url}')

    request.user = user_info

    # CSRF 防护：已登录接口的非安全方法请求，校验 X-CSRF-Token 与 csrf_token Cookie 一致（双提交）
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        csrf_header = request.headers.get('X-CSRF-Token')
        csrf_cookie = request.cookies.get('csrf_token')
        if not csrf_header or not csrf_cookie or csrf_header != csrf_cookie:
            if request.path.startswith('/api/'):
                return jsonify({"code": 403, "message": "CSRF 校验失败"}), 403
            return render_template('403.html', message="CSRF 校验失败"), 403

    if permission_level == "admin" and user_info.get("role") != "admin":
        if request.path.startswith('/api/'):
            return jsonify({"code": 403, "message": "需要管理员权限"}), 403
        return render_template('403.html', message="仅管理员可访问此接口"), 403

    return None


def admin_api(func):
    """管理端接口装饰器：显式声明需要管理员权限（落地校验）"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = _check_permission("admin")
        if result is not None:
            return result
        return func(*args, **kwargs)
    return wrapper


def wrap_view_func(view_func, plugin_name, route):
    # 兼容处理：如果 view_func 是绑定方法（bound method），取 __func__；如果是普通函数则直接用
    original_func = getattr(view_func, '__func__', view_func)

    # ==================== 统一权限解析：新版 @permission 或旧版 require_role 标记 ====================
    permission_level = _resolve_permission(original_func)
    if permission_level is None:
        permission_level = "user"  # 未声明任何权限的接口，默认仅登录

    @wraps(original_func)
    def wrapper(*args, **kwargs):
        try:
            # ==================== 统一权限校验（游客/登录/管理员三层） ====================
            auth_result = _check_permission(permission_level)
            if auth_result is not None:
                return auth_result

            # route 级上传上限（MB）注入请求上下文：
            # 1) g.plugin_route_max_upload 供 save_uploaded_file/check_upload_limit 读取；
            # 2) 同步提升 request.max_content_length（默认来自全局 MAX_CONTENT_LENGTH），
            #    使 route 级 max_upload 可突破全局默认（如 airdrop 的 GB 级大文件路由），
            #    且在本请求内作为更严格/更宽的上限兜底。
            if 'max_upload' in route:
                _route_mb = int(route.get('max_upload'))
                flask_g.plugin_route_max_upload = _route_mb
                request.max_content_length = _route_mb * 1024 * 1024

            logger.info(f"调用API: {route['path']}", extra={'plugin': plugin_name})
            increment_call_stats(plugin_name, route['path'])

            if 'params' in route:
                # 获取插件实例：优先从 __self__ 获取，如果没有则从全局 plugins 字典获取
                plugin_instance = getattr(view_func, '__self__', None)
                if plugin_instance is None:
                    plugin_instance = global_var.plugins.get(plugin_name)

                if plugin_instance and hasattr(plugin_instance, 'validate_params'):
                    validated_data, errors = plugin_instance.validate_params(route['params'])
                    if errors:
                        logger.warning(f"参数校验失败: {'; '.join(errors)}", extra={'plugin': plugin_name})
                        return plugin_instance.error_response("; ".join(errors), 400)
                    request.validated_data = validated_data
                else:
                    request.validated_data = {}

            # ==================== 关键修复：传递 kwargs（路径参数） ====================
            return view_func(*args, **kwargs)

        except AttributeError as e:
            if 'get_temp_dir' in str(e):
                err_msg = "插件基类版本过低，请更新base_plugin.py并重启服务"
                logger.error(err_msg, extra={'plugin': plugin_name})
                return jsonify({"code": 500, "message": err_msg}), 500
            raise e
        except RequestEntityTooLarge:
            # 请求体超限（413）：交给 Flask 统一 413 处理器（API JSON / 页面模板）
            raise
        except Exception as e:
            logger.error(f"API调用错误: {str(e)}\n{traceback.format_exc()}", extra={'plugin': plugin_name})
            return jsonify({"code": 500, "message": f"接口调用失败: {str(e)}"}), 500

    wrapper.__name__ = f"{plugin_name}_{route['path'].replace('/', '_')}"
    return wrapper


def wrap_page_func(page_func, plugin_name):
    @wraps(page_func.__func__)
    def wrapper(*args, **kwargs):
        try:
            # 记录插件页面访问日志，包含插件名称
            logger.info(f"访问插件页面", extra={'plugin': plugin_name})
            return page_func(*args, **kwargs)
        except Exception as e:
            logger.error(f"页面访问错误: {str(e)}\n{traceback.format_exc()}", extra={'plugin': plugin_name})
            return render_template('500.html', message=f"页面加载失败: {str(e)}"), 500
    wrapper.__name__ = f"{plugin_name}_page"
    return wrapper
