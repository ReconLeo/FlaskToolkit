# -*- coding: utf-8 -*-
"""安全中间件：统一安全响应头 + 隐藏服务器指纹

- 所有响应注入安全头（X-Content-Type-Options / X-Frame-Options / CSP / Referrer-Policy / Permissions-Policy）
- 移除 Server / X-Powered-By，隐藏框架指纹
- 通过 global_var.SECURITY_HEADERS 开关控制（默认开启，可经 config CLI 关闭）
- CSP 采用"宽"策略（允许 inline script/style）以兼容存量插件内联脚本，P1 静态扫描就绪后收紧
"""
import logging

import global_var

logger = logging.getLogger('flask.app')

# 默认安全响应头
DEFAULT_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'"
    ),
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}

# 需要移除的指纹头
REMOVE_HEADERS = ("Server", "X-Powered-By")


def register(app):
    """注册 after_request：统一注入安全响应头"""

    @app.after_request
    def add_security_headers(response):
        # 无响应体/静态 304 等场景不做处理
        if response is None:
            return response

        if global_var.SECURITY_HEADERS:
            for header, value in DEFAULT_SECURITY_HEADERS.items():
                # 插件可自行覆盖（如需要更宽/更严的 CSP 时在响应中手动设置）
                if header not in response.headers:
                    response.headers[header] = value

        # 隐藏服务器指纹（始终执行，与开关无关）
        for header in REMOVE_HEADERS:
            if header in response.headers:
                del response.headers[header]

        return response
