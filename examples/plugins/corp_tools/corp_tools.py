# -*- coding: utf-8 -*-
"""
示例插件：企业内网工具箱（corp_tools）
========================================
面向企业内网生产环境的综合示例，系统性展示框架能力：

1. **服务健康检查**：scheduled_tasks 每 60s 后台探测内网服务（HTTP HEAD→GET），
   结果缓存至插件数据目录；页面实时展示红/绿状态。网络出站经 capabilities
   白名单授权（network:http，即审计钩子的"防火墙"语义）。
2. **内部工具导航**：配置驱动链接列表，按当前用户权限（public/user/admin）过滤展示。
3. **公告板**：管理员发布/删除公告（异步落盘），登录用户查看。

框架能力展示点：插件包结构（主 .py + 辅助 .py + 多模板 + 静态资源）、
capabilities 声明、定时任务、数据目录（get_data_path 隐式豁免）、配置读写、
三层权限、多模板页面路由（page=True）、异步任务（run_async_task）、
跨插件调用（call_plugin_method 取当前用户）。

安装后访问：
- 页面   /plugin/corp_tools                     （主入口 index.html）
- 子页面 /plugin/corp_tools/health              （服务健康状态）
- 子页面 /plugin/corp_tools/links               （内部工具导航）
- 子页面 /plugin/corp_tools/notices             （公告板）
- API    GET  /api/corp_tools/health            （public：服务健康状态）
- API    GET  /api/corp_tools/links             （public：按权限过滤的导航链接）
- API    POST /api/corp_tools/links             （admin：新增导航链接）
- API    GET  /api/corp_tools/notices           （user：公告列表）
- API    POST /api/corp_tools/notices           （admin：发布公告，异步落盘）
- API    DELETE /api/corp_tools/notices/<id>    （admin：删除公告）
"""
import json
import os
import time
from typing import List, Dict

from plugins.base_plugin import BasePlugin, permission as permission_required
from plugins import corp_utils  # 辅助模块（插件包内多 .py，复用其纯函数）

# 健康探测间隔（秒，与 scheduled_tasks 保持一致；也供页面倒计时提示）
HEALTH_INTERVAL = 60
# 公告最大条数（超出丢弃最旧）
MAX_NOTICES = 100


class CorpToolsPlugin(BasePlugin):
    name = "corp_tools"
    title = "示例：企业内网工具箱"
    description = "企业内网综合示例：服务健康检查（定时探测 + 网络白名单 capabilities）+ 内部工具导航（权限过滤）+ 公告板（异步落盘），系统性展示框架多模板/权限/定时任务/配置读写/数据目录/静态资源能力。"
    version = "1.0.0"
    author = "FlaskToolkit Examples"
    category = "示例"
    permission = "user"
    require_framework_version = "4.3.2"  # get_data_path 为 v4.3.2 能力

    # 默认配置（可被 plugins/configs/corp_tools.json 覆盖，管理后台可改）
    DEFAULT_CONFIG = {
        # 健康检查服务清单：name=展示名, url=探测地址, group=分组
        "services": [
            {"name": "本机框架服务", "url": "http://127.0.0.1:5000/", "group": "核心"},
            {"name": "GitLab 内网", "url": "http://127.0.0.1:8080/", "group": "研发"},
            {"name": "文档中心", "url": "http://127.0.0.1:9000/", "group": "办公"},
        ],
        # 内部工具导航：name=展示名, url=跳转地址, group=分组, permission=可见最低权限
        "links": [
            {"name": "GitLab", "url": "http://gitlab.intra.corp/", "group": "研发", "permission": "user"},
            {"name": "Jenkins", "url": "http://jenkins.intra.corp/", "group": "研发", "permission": "admin"},
            {"name": "OA 系统", "url": "http://oa.intra.corp/", "group": "办公", "permission": "user"},
            {"name": "帮助中心", "url": "http://help.intra.corp/", "group": "公共", "permission": "public"},
        ],
    }

    def __init__(self):
        super().__init__()
        # 健康探测缓存（内存 + 落盘），scheduled_tasks 刷新
        self._health_cache = []

    # ---------------- 生命周期 ----------------
    def on_load(self):
        self.load_config()
        if not self.config or "services" not in self.config:
            self.config = dict(self.DEFAULT_CONFIG)
            self.save_config()
        # 启动即探测一次，避免首屏等待 60s
        try:
            self._probe_all()
        except Exception as e:
            self.logger.warning(f"corp_tools 初始健康探测失败: {e}")

    # ---------------- 定时任务声明（核心演示点） ----------------
    @property
    def scheduled_tasks(self) -> List[Dict]:
        return [
            {
                "func": self._probe_all,
                "trigger": "interval",
                "seconds": HEALTH_INTERVAL,
                "max_instances": 1,
            },
        ]

    # ---------------- 健康探测 ----------------
    def _probe_all(self):
        """探测所有配置服务，结果写入缓存（内存 + 插件数据目录）。"""
        services = (self.config or {}).get("services", [])
        results = []
        for svc in services:
            probe = corp_utils.probe_http(svc.get("url", ""), timeout=3.0)
            probe["name"] = svc.get("name", svc.get("url", "?"))
            probe["group"] = svc.get("group", "默认")
            results.append(probe)
        self._health_cache = results
        # 落盘（get_data_path 自属目录，隐式豁免）
        try:
            corp_utils.save_json(self.get_data_path("health.json"), results)
        except Exception as e:
            self.logger.warning(f"corp_tools 健康缓存落盘失败: {e}")

    def _get_health(self) -> List[Dict]:
        """优先内存缓存，无则读落盘文件，再兜底实时探测。"""
        if self._health_cache:
            return self._health_cache
        cached = corp_utils.load_json(self.get_data_path("health.json"), None)
        if cached:
            return cached
        self._probe_all()
        return self._health_cache

    # ---------------- 路由 ----------------
    @property
    def routes(self) -> List[Dict]:
        return [
            {
                "path": "/health",
                "name": "服务健康状态（public）",
                "methods": ["GET"],
                "params": [],
                "view_func": self.get_health,
            },
            {
                "path": "/links",
                "name": "内部工具导航（public，按权限过滤）",
                "methods": ["GET"],
                "params": [],
                "view_func": self.get_links,
            },
            {
                "path": "/links",
                "name": "新增内部工具链接（admin）",
                "methods": ["POST"],
                "params": [
                    {"name": "name", "type": "string", "required": True, "description": "展示名"},
                    {"name": "url", "type": "string", "required": True, "description": "跳转地址"},
                    {"name": "group", "type": "string", "required": False, "default": "默认", "description": "分组"},
                    {"name": "permission", "type": "string", "required": False, "default": "user", "description": "可见最低权限（public/user/admin）"},
                ],
                "view_func": self.add_link,
            },
            {
                "path": "/notices",
                "name": "公告列表（user）",
                "methods": ["GET"],
                "params": [],
                "view_func": self.get_notices,
            },
            {
                "path": "/notices",
                "name": "发布公告（admin，异步落盘）",
                "methods": ["POST"],
                "params": [
                    {"name": "title", "type": "string", "required": True, "description": "公告标题"},
                    {"name": "content", "type": "string", "required": True, "description": "公告正文"},
                    {"name": "level", "type": "string", "required": False, "default": "info", "description": "级别：info/warning/danger"},
                ],
                "view_func": self.add_notice,
            },
            {
                "path": "/notices/<notice_id>",
                "name": "删除公告（admin）",
                "methods": ["DELETE"],
                "params": [],
                "view_func": self.delete_notice,
            },
            {
                "path": "/me",
                "name": "当前用户信息（user，跨插件调 auth）",
                "methods": ["GET"],
                "params": [],
                "view_func": self.get_me,
            },
            # ---- 页面路由（page=True）：多模板子页面 ----
            {"path": "/health", "name": "服务健康状态页", "methods": ["GET"], "page": True,
             "template": "corp_tools_health.html", "view_func": self.page_health},
            {"path": "/links", "name": "内部工具导航页", "methods": ["GET"], "page": True,
             "template": "corp_tools_links.html", "view_func": self.page_links},
            {"path": "/notices", "name": "公告板页面", "methods": ["GET"], "page": True,
             "template": "corp_tools_notices.html", "view_func": self.page_notices},
        ]

    # ---------------- API 视图 ----------------
    @permission_required("public")
    def get_health(self):
        """服务健康状态（public）"""
        return self.success_response(
            data={"interval": HEALTH_INTERVAL, "items": self._get_health()},
            message="服务健康状态获取成功",
        )

    @permission_required("public")
    def get_links(self):
        """内部工具导航（public，按当前用户权限过滤）"""
        role = self._current_role()
        links = corp_utils.filter_links((self.config or {}).get("links", []), role)
        return self.success_response(
            data={"role": role, "items": links},
            message="导航链接获取成功",
        )

    @permission_required("admin")
    def add_link(self):
        """新增内部工具链接（admin）"""
        from flask import request
        data = request.validated_data
        self.load_config()
        cfg = self.config or dict(self.DEFAULT_CONFIG)
        perm = data.get("permission", "user")
        if perm not in ("public", "user", "admin"):
            return self.error_response("permission 仅支持 public/user/admin", code=400)
        link = {
            "name": data["name"],
            "url": data["url"],
            "group": data.get("group", "默认"),
            "permission": perm,
        }
        cfg.setdefault("links", []).append(link)
        self.config = cfg
        self.save_config()
        return self.success_response(data={"link": link}, message="导航链接已添加")

    @permission_required("user")
    def get_notices(self):
        """公告列表（user，倒序）"""
        notices = self._load_notices()
        return self.success_response(
            data={"items": corp_utils.sort_notices(notices)},
            message="公告列表获取成功",
        )

    @permission_required("admin")
    def add_notice(self):
        """发布公告（admin，异步落盘展示 run_async_task）"""
        from flask import request
        data = request.validated_data
        level = data.get("level", "info")
        if level not in ("info", "warning", "danger"):
            return self.error_response("level 仅支持 info/warning/danger", code=400)
        notice = {
            "id": str(int(time.time() * 1000)),
            "title": data["title"],
            "content": data["content"],
            "level": level,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "author": self._current_username(),
        }
        # 异步落盘：不阻塞请求（真实场景可接通知推送）
        self.run_async_task(self._append_notice, notice)
        return self.success_response(data={"notice": notice}, message="公告发布成功（异步落盘）")

    @permission_required("admin")
    def delete_notice(self, notice_id: str):
        """删除公告（admin）"""
        notices = self._load_notices()
        remain = [n for n in notices if n.get("id") != notice_id]
        if len(remain) == len(notices):
            return self.error_response(f"公告 {notice_id} 不存在", code=404)
        self._save_notices(remain)
        return self.success_response(message="公告已删除")

    @permission_required("user")
    def get_me(self):
        """当前用户信息（user，跨插件调 auth 展示 call_plugin_method）"""
        username = self._current_username()
        role = self._current_role()
        extra = {}
        try:
            # 跨插件调用：auth 未安装时回退基础信息
            users = self.call_plugin_method("auth", "get_all_users") or []
            extra["total_users"] = len(users)
        except Exception:
            extra["auth_plugin"] = "not installed"
        return self.success_response(
            data={"username": username, "role": role, **extra},
            message="当前用户信息获取成功",
        )

    # ---------------- 公告持久化 ----------------
    def _notices_path(self) -> str:
        return self.get_data_path("notices.json")

    def _load_notices(self) -> List[Dict]:
        return corp_utils.load_json(self._notices_path(), [])

    def _save_notices(self, notices: List[Dict]):
        corp_utils.save_json(self._notices_path(), notices[-MAX_NOTICES:])

    def _append_notice(self, notice: Dict):
        """异步任务函数：追加公告并落盘（由 run_async_task 在后台线程执行）。"""
        notices = self._load_notices()
        notices.append(notice)
        self._save_notices(notices)

    # ---------------- 页面视图 ----------------
    def render_index(self) -> Dict:
        """主入口 index.html 数据钩子"""
        health = self._get_health()
        up_count = sum(1 for h in health if h.get("up"))
        return {
            "name": self.name,
            "title": self.title,
            "username": self._current_username(),
            "role": self._current_role(),
            "health": {"total": len(health), "up": up_count},
            "sub_pages": [r["path"] for r in self.routes if r.get("page")],
        }

    def page_health(self):
        return {"interval": HEALTH_INTERVAL, "name": self.name}

    def page_links(self):
        return {"name": self.name, "role": self._current_role()}

    def page_notices(self):
        return {"name": self.name}

    # ---------------- 辅助 ----------------
    def _current_username(self) -> str:
        """取当前登录用户名（request.user 由全局鉴权拦截器注入）"""
        from flask import request
        user = getattr(request, "user", None)
        if isinstance(user, dict) and user.get("username"):
            return user["username"]
        return "未登录"

    def _current_role(self) -> str:
        """取当前用户角色（public/user/admin），用于导航链接过滤"""
        from flask import request
        user = getattr(request, "user", None)
        if isinstance(user, dict):
            role = user.get("role", "user")
            return role if role in ("public", "user", "admin") else "user"
        return "public"
