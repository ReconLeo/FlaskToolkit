# -*- coding: utf-8 -*-
"""插件路由：插件页面/API 分发、插件列表、手动重载"""
import os
import re
import traceback

from flask import Response, jsonify, render_template, request

import global_var
from core.plugin_loader import load_plugins
from core.utils import parse_path_pattern


def register(app):
    @app.route('/plugin-static/<plugin_name>/<path:filename>')
    def serve_plugin_static(plugin_name, filename):
        """
        插件静态资源通配路由（启动时注册一次，热加载友好）。
        运行时按插件名分发到其 static_dir：优先插件实例自定义目录，
        否则回退默认目录 templates/plugins/static/<插件名>/。
        """
        import os
        from flask import send_from_directory

        plugin = global_var.plugins.get(plugin_name)
        if plugin is not None and getattr(plugin, 'static_dir', None):
            static_dir = plugin.static_dir
        else:
            static_dir = os.path.join(
                global_var.BASE_DIR, 'templates', 'plugins', 'static', plugin_name
            )
        if not os.path.isdir(static_dir):
            return render_template('404.html', message=f"插件 {plugin_name} 静态资源不存在"), 404
        return send_from_directory(static_dir, filename)

    @app.route('/plugin/<plugin_name>')
    def plugin_page_dispatcher(plugin_name):
        plugin = global_var.plugins.get(plugin_name)
        if plugin is None:
            return render_template('404.html', message=f"插件 {plugin_name} 不存在或未加载"), 404
        if not plugin.enabled or not hasattr(plugin, '_wrapped_page'):
            return render_template('404.html', message=f"插件 {plugin_name} 已禁用或未加载"), 404
        return plugin._wrapped_page()

    @app.route('/plugin/<plugin_name>/<path:sub_page>', methods=['GET', 'POST'])
    def plugin_subpage_dispatcher(plugin_name, sub_page):
        """插件子页面路由（大插件多模板支持）：按插件声明的 page 路由分发。
        view_func 返回 dict → 渲染到插件模板（自动定位命名空间）；返回 Response → 原样返回。"""
        plugin = global_var.plugins.get(plugin_name)
        if plugin is None or not getattr(plugin, 'enabled', False) or not hasattr(plugin, '_wrapped_pages'):
            return render_template('404.html', message=f"插件 {plugin_name} 不存在或未加载"), 404
        if not plugin._wrapped_pages:
            return render_template('404.html', message=f"插件 {plugin_name} 无子页面"), 404

        sub_path = sub_page if sub_page.startswith('/') else '/' + sub_page
        entry = None
        kwargs = {}
        # 精确匹配
        if sub_path in plugin._wrapped_pages:
            entry = plugin._wrapped_pages[sub_path]
        else:
            # 正则匹配（路径参数，如 /status/<task_id>）
            for path, cand in plugin._wrapped_pages.items():
                if '<' in path:
                    pattern, param_names = parse_path_pattern(path)
                    m = re.match(pattern, sub_path)
                    if m:
                        entry = cand
                        kwargs = {param_names[i]: m.group(i + 1) for i in range(len(param_names))}
                        break
        if entry is None:
            return render_template('404.html', message=f"插件子页面不存在: {sub_page}"), 404

        try:
            result = entry['view_func'](**kwargs)
        except Exception as e:
            logger = app.logger
            logger.error(f"插件子页面渲染错误: {str(e)}\n{traceback.format_exc()}", extra={'plugin': plugin_name})
            return render_template('500.html', message=f"页面加载失败: {str(e)}"), 500
        if isinstance(result, Response):
            return result
        resolved = plugin._resolve_template(entry['template']) if hasattr(plugin, '_resolve_template') else None
        if resolved is None:
            resolved = f'plugins/{plugin_name}/{entry["template"].replace(chr(92), "/")}'
        ctx = result if isinstance(result, dict) else {}
        return render_template(resolved, plugin=plugin, **ctx)

    @app.route('/api/<plugin_name>/<path:api_path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
    def api_dispatcher(plugin_name, api_path):
        if plugin_name not in global_var.plugins:
            return jsonify({"code": 404, "message": f"插件 {plugin_name} 不存在或未加载"}), 404

        plugin = global_var.plugins[plugin_name]
        if not plugin.enabled or not hasattr(plugin, '_wrapped_routes'):
            return jsonify({"code": 404, "message": f"插件 {plugin_name} 已禁用"}), 404

        api_full_path = f"/{api_path}"

        # 修复：支持根路径API（如/config）
        if not api_path and '/' in plugin._wrapped_routes:
            api_full_path = '/'

        # ==================== 修复：路径参数匹配 ====================
        # 先尝试精确匹配
        matched_view_func = None
        matched_kwargs = {}

        if api_full_path in plugin._wrapped_routes:
            # 精确匹配成功
            route_methods = plugin._wrapped_routes[api_full_path]
            for supported_methods, view_func in route_methods.items():
                if request.method in supported_methods:
                    matched_view_func = view_func
                    break
        else:
            # 精确匹配失败，尝试正则匹配（处理路径参数）
            for registered_path, route_methods in plugin._wrapped_routes.items():
                # 检查该路径是否包含参数
                if '<' in registered_path:
                    pattern, param_names = parse_path_pattern(registered_path)
                    match = pattern.match(api_full_path)
                    if match:
                        # 提取参数值
                        kwargs = dict(zip(param_names, match.groups()))
                        for supported_methods, view_func in route_methods.items():
                            if request.method in supported_methods:
                                matched_view_func = view_func
                                matched_kwargs = kwargs
                                break
                        if matched_view_func:
                            break

        if matched_view_func is None:
            # 检查路径是否存在（仅方法不匹配）
            path_exists = (
                api_full_path in plugin._wrapped_routes or
                any('<' in path for path in plugin._wrapped_routes)
            )
            if path_exists:
                # 收集所有支持的方法
                allowed_methods = set()
                for registered_path, route_methods in plugin._wrapped_routes.items():
                    if registered_path == api_full_path or ('<' in registered_path and
                        parse_path_pattern(registered_path)[0].match(api_full_path)):
                        for methods in route_methods.keys():
                            allowed_methods.update(methods)
                return jsonify({
                    "code": 405,
                    "message": f"不支持的请求方法 {request.method}，支持的方法: {', '.join(allowed_methods)}"
                }), 405
            else:
                return jsonify({"code": 404, "message": f"API路径 {api_full_path} 不存在"}), 404

        # ==================== 调用视图函数（传入路径参数） ====================
        return matched_view_func(**matched_kwargs)

    @app.route('/api/plugins')
    def get_plugins():
        plugin_list = [{
            'name': p.name,
            'description': p.description,
            'version': p.version,
            'category': p.category,
            'page_url': f'/plugin/{p.name}'
        } for p in global_var.plugins.values()]
        return jsonify({"code": 200, "data": plugin_list, "message": "获取成功"})

    @app.route('/api/reload')
    def manual_reload():
        try:
            load_plugins()
            return jsonify({"code": 200, "message": "插件重载成功"})
        except Exception as e:
            return jsonify({"code": 500, "message": f"重载失败: {str(e)}"})
