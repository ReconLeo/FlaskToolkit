# -*- coding: utf-8 -*-
"""
示例插件：Hello 脚手架（hello_plugin）
========================================
展示框架的核心插件能力，作为新插件开发的起始模板：

1. 生命周期钩子：on_load / on_shutdown / on_unload / on_uninstall
2. 三层权限路由：public（游客）/ user（登录）/ admin（管理员）
3. 配置持久化：load_config / save_config（存于 plugins/configs/<name>.json）
4. 自定义页面：/plugin/hello_plugin 渲染自定义模板

安装方式见 examples/README.md。安装后可访问：
- 页面   /plugin/hello_plugin
- API    /api/hello_plugin/public   （游客可访问）
- API    /api/hello_plugin/user     （登录后可访问）
- API    /api/hello_plugin/admin    （仅管理员）
"""
from typing import List, Dict

from flask import request

from plugins.base_plugin import BasePlugin, permission as permission_required


class HelloPlugin(BasePlugin):
    name = "hello_plugin"
    title = "示例：Hello 脚手架"
    description = "基础插件模板：生命周期钩子（on_load/on_shutdown/on_unload/on_uninstall）+ 三层权限路由（public/user/admin）+ 配置读写 + 自定义页面，展示一个插件能做什么。"
    version = "1.0.0"
    author = "FlaskToolkit Examples"
    category = "示例"
    permission = "user"
    require_framework_version = "4.1.0"

    # 默认配置（可被 plugins/configs/hello_plugin.json 覆盖）
    DEFAULT_CONFIG = {
        "greeting": "你好，FlaskToolkit！",
        "show_timestamp": True,
        "visits": 0,
    }

    # ---------------- 生命周期钩子 ----------------
    def on_load(self):
        """插件加载完成后调用：用于初始化（如注册定时任务、加载配置）"""
        # 加载持久化配置（load_config 无返回值，结果写入 self.config）
        self.load_config()
        if not self.config:
            self.config = dict(self.DEFAULT_CONFIG)
            self.save_config()  # save_config 不接收参数，保存 self.config
        self.logger.info(f"hello_plugin 加载完成，greeting={self.config.get('greeting')}")

    def on_shutdown(self):
        """服务停止前调用：用于清理资源、持久化状态"""
        self.logger.info("hello_plugin 正在停止，执行清理...")

    def on_unload(self):
        """插件被卸载（文件删除）前调用"""
        self.logger.info("hello_plugin 被卸载")

    def on_uninstall(self):
        """插件被正式卸载时调用（可清理本插件产生的数据）"""
        self.logger.info("hello_plugin 已卸载，清理示例数据")

    # ---------------- 路由 ----------------
    @property
    def routes(self) -> List[Dict]:
        return [
            {
                "path": "/public",
                "name": "游客接口（public 权限）",
                "methods": ["GET"],
                "params": [
                    {"name": "name", "type": "string", "required": False, "default": "游客", "description": "称呼"}
                ],
                "view_func": self.api_public,
            },
            {
                "path": "/user",
                "name": "登录用户接口（user 权限）",
                "methods": ["GET"],
                "params": [],
                "view_func": self.api_user,
            },
            {
                "path": "/admin",
                "name": "管理员接口（admin 权限）",
                "methods": ["GET"],
                "params": [],
                "view_func": self.api_admin,
            },
            {
                "path": "/config",
                "name": "读取配置（user 权限）",
                "methods": ["GET"],
                "params": [],
                "view_func": self.get_config,
            },
            {
                "path": "/config",
                "name": "保存配置（admin 权限）",
                "methods": ["POST"],
                "params": [
                    {"name": "greeting", "type": "string", "required": False, "description": "问候语"},
                    {"name": "show_timestamp", "type": "boolean", "required": False, "description": "页面是否显示时间戳"}
                ],
                "view_func": self.save_config_api,
            },
        ]

    # ---------------- 视图函数 ----------------
    @permission_required("public")
    def api_public(self):
        """游客可访问：演示 public 权限"""
        name = request.validated_data.get("name", "游客")
        return self.success_response(
            data={"message": f"{name}，你好！public 接口无需登录。"},
            message="public 接口调用成功",
        )

    @permission_required("user")
    def api_user(self):
        """登录后可访问：演示 user 权限"""
        username = self._current_username()
        return self.success_response(
            data={"message": f"{username}，你好！user 接口需要登录。",
                  "username": username},
            message="user 接口调用成功",
        )

    @permission_required("admin")
    def api_admin(self):
        """仅管理员可访问：演示 admin 权限"""
        return self.success_response(
            data={"message": "admin 接口仅管理员可访问。",
                  "username": self._current_username()},
            message="admin 接口调用成功",
        )

    @permission_required("user")
    def get_config(self):
        """读取当前配置"""
        self.load_config()
        cfg = self.config or dict(self.DEFAULT_CONFIG)
        # 访问次数 +1 并持久化，演示配置写入
        cfg["visits"] = cfg.get("visits", 0) + 1
        self.config = cfg
        self.save_config()
        return self.success_response(data=cfg, message="配置读取成功")

    @permission_required("admin")
    def save_config_api(self):
        """保存配置（仅管理员）"""
        self.load_config()
        cfg = self.config or dict(self.DEFAULT_CONFIG)
        for key in ("greeting", "show_timestamp"):
            if key in request.validated_data:
                cfg[key] = request.validated_data[key]
        self.config = cfg
        self.save_config()
        return self.success_response(data=cfg, message="配置已保存")

    # ---------------- 页面 ----------------
    def page(self):
        """自定义插件页面：渲染 templates/plugins/hello_plugin.html"""
        self.load_config()
        cfg = self.config or dict(self.DEFAULT_CONFIG)
        from flask import render_template
        return render_template(
            "plugins/hello_plugin.html",
            plugin=self,
            config=cfg,
            username=self._current_username(),
        )

    # ---------------- 辅助 ----------------
    def _current_username(self) -> str:
        """取当前登录用户名（request.user 由全局鉴权拦截器注入，未登录返回 '未登录'）"""
        from flask import request
        user = getattr(request, "user", None)
        if isinstance(user, dict) and user.get("username"):
            return user["username"]
        return "未登录"
