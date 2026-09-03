# -*- coding: utf-8 -*-
"""
路由层（routes）：按职责分组的 Flask 路由注册

- 各模块提供 register(app) 函数，内部通过 @app.route / @app.before_request 注册。
- 统一入口 register_routes(app)：按【拦截器 → 公开 → 插件 → 前端工具 → 管理端】顺序注册。
- 路由函数依赖的共享状态一律通过 global_var 引用，服务逻辑从 core 包导入。
"""


def register_routes(app):
    """聚合注册全部路由（拦截器、公开、插件、前端工具、管理端、安全）"""
    from routes import interceptor, public, plugin, frontend, admin, security

    interceptor.register(app)
    public.register(app)
    plugin.register(app)
    frontend.register(app)
    admin.register(app)
    security.register(app)
