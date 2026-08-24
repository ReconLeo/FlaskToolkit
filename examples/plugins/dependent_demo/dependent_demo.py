# -*- coding: utf-8 -*-
"""
示例插件：插件依赖与跨插件调用（dependent_demo）
==================================================
展示框架的插件间协作能力：

1. dependencies 依赖声明：本插件依赖 auth 插件（用户数据与鉴权能力）。
   - 安装时：若 auth 未安装，插件包校验会拒绝安装。
   - 加载时：插件加载器做拓扑排序，先加载依赖；auth 缺失则拒绝加载并给出提示。
2. call_plugin_method 跨插件调用：直接调用 auth 插件的公开方法
   （get_all_users / get_user_by_username），无需重复实现用户数据逻辑。

安装后访问：
- 页面 /plugin/dependent_demo
- API  GET /api/dependent_demo/users            （跨插件调用 auth.get_all_users，admin 权限）
- API  GET /api/dependent_demo/user/<username>  （跨插件调用 auth.get_user_by_username，user 权限）
"""
from typing import List, Dict

from flask import request
from plugins.base_plugin import BasePlugin, permission as permission_required


class DependentDemoPlugin(BasePlugin):
    name = "dependent_demo"
    title = "示例：插件依赖与跨插件调用"
    description = "依赖与协作示例：声明 dependencies 依赖 auth 插件（未安装时框架拒绝加载并提示缺失），通过 call_plugin_method 跨插件调用 auth 的用户数据能力。"
    version = "1.0.0"
    author = "FlaskToolkit Examples"
    category = "示例"
    permission = "user"
    dependencies = ["auth"]  # 依赖声明：加载器先加载 auth，缺失则拒绝加载
    require_framework_version = "4.1.0"

    # ---------------- 路由 ----------------
    @property
    def routes(self) -> List[Dict]:
        return [
            {
                "path": "/users",
                "name": "获取全部用户（跨插件调用 auth.get_all_users）",
                "methods": ["GET"],
                "params": [],
                "view_func": self.get_users,
            },
            {
                "path": "/user/<username>",
                "name": "按用户名查询（跨插件调用 auth.get_user_by_username）",
                "methods": ["GET"],
                # username 为路径参数（URL 中传递），框架路径匹配后作为 view_func 的 kwargs 注入，
                # 无需在 params 中声明（params 只用于 query/body 参数校验）。
                "params": [],
                "view_func": self.get_user,
            },
        ]

    @permission_required("admin")
    def get_users(self):
        """跨插件调用 auth.get_all_users（仅管理员可访问）"""
        try:
            users = self.call_plugin_method("auth", "get_all_users")
            # 脱敏：只暴露必要字段
            safe = [
                {"id": u.get("id"), "username": u.get("username"),
                 "role": u.get("role"), "nickname": u.get("nickname")}
                for u in (users or [])
            ]
            return self.success_response(
                data={"count": len(safe), "users": safe},
                message="跨插件调用成功：auth.get_all_users",
            )
        except (ValueError, RuntimeError) as e:
            return self.error_response(str(e), code=500)

    @permission_required("user")
    def get_user(self, username: str):
        """跨插件调用 auth.get_user_by_username（登录用户可访问）"""
        try:
            user = self.call_plugin_method("auth", "get_user_by_username", username)
            if not user:
                return self.error_response(f"用户 {username} 不存在", code=404)
            safe = {
                "id": user.get("id"),
                "username": user.get("username"),
                "role": user.get("role"),
                "nickname": user.get("nickname"),
            }
            return self.success_response(
                data={"user": safe},
                message=f"跨插件调用成功：auth.get_user_by_username('{username}')",
            )
        except (ValueError, RuntimeError) as e:
            return self.error_response(str(e), code=500)

    # ---------------- 页面 ----------------
    def page(self):
        return self.render("dependent_demo.html")
