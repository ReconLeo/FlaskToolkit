# -*- coding: utf-8 -*-
"""
示例插件：插件依赖 + 跨插件调用 + 跨插件事件（dependent_demo）
==============================================================
展示框架的插件间协作能力（含 v4.16 事件总线）：

1. dependencies 依赖声明：本插件依赖 auth 插件（用户数据与鉴权能力）。
   - 安装时：若 auth 未安装，插件包校验会拒绝安装。
   - 加载时：插件加载器做拓扑排序，先加载依赖；auth 缺失则拒绝加载并给出提示。
2. call_plugin_method 跨插件调用：直接调用 auth 插件的公开方法
   （get_all_users / get_user_by_username），无需重复实现用户数据逻辑。
3. 跨插件事件订阅（v4.16 事件总线，BasePlugin.on_event）：
   - 事件总线让插件间**松耦合**通信——订阅方不需要依赖声明、不需要调用被订阅方的方法，
     即可感知其状态变化。本插件：
     * 订阅 scheduler_demo 发布的自定义事件（plugin:scheduler_demo:heartbeat/stats/manual_trigger）——
       即使未安装 scheduler_demo，本插件也能正常加载运行（只是收不到那些事件），这正是事件总线解耦的价值；
     * 订阅内置全局事件（user.login / user.logout / plugin.loaded / request.finished）。
   - 收到事件后写入事件历史（持久化），页面实时展示『跨插件事件接收』清单。

安装后访问：
- 页面 /plugin/dependent_demo
- API  GET /api/dependent_demo/users            （跨插件调用 auth.get_all_users，admin 权限）
- API  GET /api/dependent_demo/user/<username>  （跨插件调用 auth.get_user_by_username，user 权限）
- API  GET /api/dependent_demo/events           （跨插件/全局事件接收历史，user 权限）
"""
import json
import os
import time
from typing import List, Dict

from flask import request
from plugins.base_plugin import BasePlugin, permission as permission_required

# 事件历史最大保留条数
MAX_EVENTS = 200


class DependentDemoPlugin(BasePlugin):
    name = "dependent_demo"
    title = "示例：插件依赖 + 跨插件调用 + 跨插件事件"
    description = "依赖与协作示例：声明 dependencies 依赖 auth 插件（缺失拒绝加载），通过 call_plugin_method 跨插件调用 auth 的用户数据能力，并通过 v4.16 事件总线松耦合订阅 scheduler_demo 与框架全局事件（跨插件事件接收）。"
    version = "2.0.0"
    author = "FlaskToolkit Examples"
    category = "示例"
    permission = "user"
    dependencies = ["auth"]  # 依赖声明：加载器先加载 auth，缺失则拒绝加载
    require_framework_version = "4.16.0"  # on_event 为 v4.16 BasePlugin 事件集成

    # ---------------- v4.16 跨插件事件订阅 ----------------
    def on_load(self):
        """订阅跨插件事件（scheduler_demo 自定义事件）+ 内置全局事件。

        说明：订阅 scheduler_demo 事件属**松耦合**——本插件并未在 dependencies 声明
        scheduler_demo，即使其未安装也能正常加载，只是收不到对应事件。
        """
        # 跨插件：订阅 scheduler_demo 发布的自定义事件（无需依赖声明/方法调用即可感知）
        for ev in ('heartbeat', 'stats', 'manual_trigger'):
            self.on_event(f'plugin:scheduler_demo:{ev}', self._on_event)
        # 框架内置全局事件
        for ev in ('user.login', 'user.logout', 'plugin.loaded', 'request.finished'):
            self.on_event(ev, self._on_event)

    def _on_event(self, event, **data):
        """事件订阅回调：写入跨插件/全局事件历史。"""
        source = self._source_of(event)
        entry = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "event": event,
            "source": source,
            "data": json.dumps(data, ensure_ascii=False),
        }
        evs = self._load_events()
        evs.append(entry)
        if len(evs) > MAX_EVENTS:
            evs = evs[-MAX_EVENTS:]
        self._save_events(evs)

    @staticmethod
    def _source_of(event: str) -> str:
        """事件来源归属：plugin:<插件名>:<事件名> → 跨插件来源；其余 → 框架全局。"""
        if event.startswith('plugin:') and ':' in event[7:]:
            return '跨插件(' + event.split(':')[1] + ')'
        return '框架全局'

    @property
    def events_file(self):
        return self.get_data_path('events.json')

    def _load_events(self) -> List[Dict]:
        if not os.path.exists(self.events_file):
            return []
        try:
            with open(self.events_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_events(self, data: List[Dict]):
        with open(self.events_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

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
            {
                "path": "/events",
                "name": "跨插件/全局事件接收历史",
                "methods": ["GET"],
                "params": [
                    {"name": "limit", "type": "number", "required": False, "default": 20, "description": "返回条数"}
                ],
                "view_func": self.get_events,
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

    @permission_required("user")
    def get_events(self):
        """查询跨插件/全局事件接收历史（user 权限）"""
        limit = int(request.validated_data.get("limit", 20))
        data = self._load_events()
        return self.success_response(
            data={"total": len(data), "items": data[-limit:]},
            message="跨插件事件接收历史查询成功",
        )

    # ---------------- 页面 ----------------
    def page(self):
        events = self._load_events()
        return self.render(
            "dependent_demo.html",
            events=events[-20:],
            total=len(events),
        )
