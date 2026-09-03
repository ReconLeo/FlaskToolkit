# -*- coding: utf-8 -*-
"""
示例插件：Hello 脚手架（hello_plugin）
========================================
展示框架的核心插件能力，作为新插件开发的起始模板：

1. 生命周期钩子：on_load / on_shutdown / on_unload / on_uninstall
2. 三层权限路由：public（游客）/ user（登录）/ admin（管理员）
3. 配置持久化：load_config / save_config（存于 plugins/configs/<name>.json）
4. 自定义页面：/plugin/hello_plugin 渲染自定义模板（page() 旧式自定义入口）
5. 多模板子页面：页面路由 page=True（主入口 + 功能分担子页 + 路径参数子页）

安装方式见 examples/README.md。安装后可访问：
- 页面   /plugin/hello_plugin                     （主入口，自定义页面）
- 子页面 /plugin/hello_plugin/about               （功能分担：关于）
- 子页面 /plugin/hello_plugin/usage               （功能分担：接口说明）
- 子页面 /plugin/hello_plugin/greet/小明          （路径参数子页）
- API    /api/hello_plugin/public   （游客可访问）
- API    /api/hello_plugin/user     （登录后可访问）
- API    /api/hello_plugin/admin    （仅管理员）
"""
import json
import os
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
    require_framework_version = "4.2.0"

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
                "path": "/data-demo",
                "name": "数据目录演示（public，v4.3.2）",
                "methods": ["GET"],
                "params": [],
                "view_func": self.api_data_demo,
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
            # ---- 页面路由（page=True）：多模板子页面，不进 API 分发，走 /plugin/<name>/<sub_page> ----
            # view_func 返回 dict → 分发器渲染命名空间模板；返回 Response（self.render）→ 原样返回
            {
                "path": "/about", "name": "关于本插件", "methods": ["GET"],
                "page": True, "template": "about.html", "view_func": self.page_about,
            },
            {
                "path": "/usage", "name": "接口使用说明", "methods": ["GET"],
                "page": True, "template": "usage.html", "view_func": self.page_usage,
            },
            {
                "path": "/greet/<name>", "name": "问候子页（路径参数）", "methods": ["GET"],
                "page": True, "template": "greet.html", "view_func": self.page_greet,
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

    @permission_required("public")
    def api_data_demo(self):
        """游客可访问：演示插件专属数据目录（v4.3.2 get_data_path）
        写入 plugins/data/hello_plugin/visits.json —— 自属路径隐式豁免，无需声明 capabilities"""
        path = self.get_data_path('visits.json')
        visits = 0
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    visits = json.load(f).get("visits", 0)
            except Exception:
                visits = 0
        visits += 1
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"visits": visits}, f, ensure_ascii=False)
        return self.success_response(
            data={"visits": visits, "data_file": path.replace("\\", "/")},
            message="插件数据目录读写成功（隐式豁免，无需声明）",
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
        """自定义插件主入口：渲染模板命名空间下的 hello_plugin.html
        （page() 为旧式自定义入口，框架检测到插件类定义了 page() 即优先调用；
         self.render 会自动定位到 templates/plugins/hello_plugin/ 命名空间）"""
        self.load_config()
        cfg = self.config or dict(self.DEFAULT_CONFIG)
        return self.render(
            "hello_plugin.html",
            config=cfg,
            username=self._current_username(),
        )

    # ---- 页面路由（page=True）子页面：由 routes/plugin.py 的 /plugin/<name>/<path:sub_page> 分发 ----
    def page_about(self):
        """子页面：关于本插件（返回 dict → 分发器渲染 about.html）"""
        return {
            "features": ["生命周期钩子", "三层权限路由", "配置持久化", "多模板子页面", "插件包机制"],
            "name": self.name,
            "version": self.version,
        }

    def page_usage(self):
        """子页面：接口使用说明（返回 dict → 分发器渲染 usage.html）"""
        self.load_config()
        cfg = self.config or dict(self.DEFAULT_CONFIG)
        return {
            "apis": [r["path"] for r in self.routes if not r.get("page")],
            "base": f"/api/{self.name}",
            "greeting": cfg.get("greeting", "你好！"),
        }

    def page_greet(self, name):
        """子页面：路径参数演示（<name> 注入 kwargs → 分发器渲染 greet.html）"""
        self.load_config()
        cfg = self.config or dict(self.DEFAULT_CONFIG)
        return {"name": name, "greeting": cfg.get("greeting", "你好！")}

    # ---------------- 辅助 ----------------
    def _current_username(self) -> str:
        """取当前登录用户名（request.user 由全局鉴权拦截器注入，未登录返回 '未登录'）"""
        from flask import request
        user = getattr(request, "user", None)
        if isinstance(user, dict) and user.get("username"):
            return user["username"]
        return "未登录"
