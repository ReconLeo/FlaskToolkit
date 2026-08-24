# -*- coding: utf-8 -*-
"""
示例插件：大插件多模板（multitool_demo）
========================================
演示"大插件"三要素：多模板 + 辅助 .py + 静态资源。

1. 多模板：主入口 index.html + 3 个子页面（页面路由 page=True）
2. 辅助 .py：multitool_utils.py（与主 .py 分离的纯函数模块，供 API 与视图复用）
3. 静态资源：static/css/demo.css + static/js/demo.js（经 /plugin-static/ 访问）

安装后可访问（功能点到为止，文本分析工具示例）：
- 页面   /plugin/multitool_demo                        （主入口 index.html，引用静态资源）
- 子页面 /plugin/multitool_demo/text                   （文本统计：静态 JS 调 API）
- 子页面 /plugin/multitool_demo/topwords               （词频 Top-N：辅助模块服务端渲染）
- 子页面 /plugin/multitool_demo/hello/小明             （路径参数子页）
- API    /api/multitool_demo/analyze        [POST]     （文本分析，复用辅助模块）
"""
from typing import List, Dict

from flask import request

from plugins.base_plugin import BasePlugin, permission as permission_required
from plugins import multitool_utils  # 辅助模块（插件包内多 .py，复用其纯函数）


class MultiToolDemo(BasePlugin):
    name = "multitool_demo"
    title = "示例：大插件多模板"
    description = "大插件三要素演示：多模板（主入口 + 3 子页）+ 辅助 .py（multitool_utils）+ 静态资源（css/js）。文本分析小工具。"
    version = "1.0.0"
    author = "FlaskToolkit Examples"
    category = "示例"
    permission = "user"

    @property
    def routes(self) -> List[Dict]:
        return [
            {
                "path": "/analyze",
                "name": "文本分析（user 权限）",
                "methods": ["POST"],
                "params": [
                    {"name": "text", "type": "string", "required": True, "description": "待分析文本"}
                ],
                "view_func": self.api_analyze,
            },
            # ---- 页面路由（page=True）：多模板子页，走 /plugin/<name>/<sub_page> ----
            {"path": "/text", "name": "文本统计", "methods": ["GET"], "page": True,
             "template": "text.html", "view_func": self.page_text},
            {"path": "/topwords", "name": "词频 Top-N", "methods": ["GET"], "page": True,
             "template": "topwords.html", "view_func": self.page_topwords},
            {"path": "/hello/<name>", "name": "问候子页（路径参数）", "methods": ["GET"], "page": True,
             "template": "hello.html", "view_func": self.page_hello},
        ]

    # ---- 主入口 index.html 的数据钩子（render_index 返回上下文 dict） ----
    def render_index(self) -> Dict:
        return {
            "name": self.name,
            "title": self.title,
            "sub_pages": [r["path"] for r in self.routes if r.get("page")],
            "has_helper": True,
            "has_static": True,
        }

    # ---- API（复用辅助模块 multitool_utils） ----
    @permission_required("user")
    def api_analyze(self):
        text = request.validated_data.get("text", "")
        stats = multitool_utils.analyze_text(text)
        top = multitool_utils.top_words(text, 5)
        return self.success_response(
            data={"stats": stats, "top_words": top},
            message="文本分析完成",
        )

    # ---- 页面路由（page=True）视图函数 ----
    def page_text(self):
        # dict → 分发器渲染 text.html（页面内静态 JS 负责调 API）
        return {"api_url": f"/api/{self.name}/analyze"}

    def page_topwords(self):
        # 服务端渲染：辅助模块直接计算示例文本的词频 Top-N
        sample = "你好 Flask 你好 框架 你好 Flask 插件 插件 插件"
        return {"sample": sample, "top": multitool_utils.top_words(sample, 5)}

    def page_hello(self, name):
        # 路径参数 <name> 由分发器注入 kwargs → 渲染 hello.html
        return {"name": name, "title": self.title}
