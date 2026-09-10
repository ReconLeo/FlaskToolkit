# -*- coding: utf-8 -*-
"""
示例插件：APScheduler 定时任务 + 事件总线（scheduler_demo）
============================================================
展示框架的定时任务能力与 v4.16 事件总线集成：

1. scheduled_tasks 属性：声明定时任务，框架加载插件时自动注册到 APScheduler。
   - interval 触发器：每 30 秒执行一次心跳
   - cron 触发器：每分钟整点执行一次统计
2. 定时任务写入心跳记录（内存 + 持久化到 data/scheduler_demo/heartbeats.json）。
3. v4.16 事件总线演示（BasePlugin 集成）：
   - on_load 订阅内置全局事件（user.login / plugin.loaded / request.finished）；
   - 定时任务触发时发布自定义事件（emit_event：heartbeat / stats）；
   - 订阅自身自定义事件（event_name 前缀 plugin:scheduler_demo:heartbeat/stats，含页面手动发布的 manual_trigger）；
   - 同步 + 异步（async_=True）订阅；
   - 事件历史持久化到 data/scheduler_demo/events.json，页面实时展示。
4. 查询 API 与自定义页面：实时展示心跳/统计/事件历史。

安装后访问：
- 页面 /plugin/scheduler_demo
- API  /api/scheduler_demo/heartbeats   （最近 N 条心跳，user）
- API  /api/scheduler_demo/stats        （任务统计，user）
- API  /api/scheduler_demo/events       （GET 事件历史，user / DELETE 清空，admin）
- API  /api/scheduler_demo/emit_event   （POST 手动发布自定义事件，user）
"""
import json
import os
import time
from typing import List, Dict

from plugins.base_plugin import BasePlugin, permission as permission_required

# 心跳 / 事件最大保留条数
MAX_HEARTBEATS = 200
MAX_EVENTS = 200


class SchedulerDemoPlugin(BasePlugin):
    name = "scheduler_demo"
    title = "示例：APScheduler 定时任务 + 事件总线"
    description = "定时任务 + 事件总线示例：通过 scheduled_tasks 声明 interval/cron 触发器定时写入心跳，并由 BasePlugin 事件集成订阅/发布事件（内置事件订阅、自定义事件发布订阅、同步/异步），页面实时展示调度与事件历史。"
    version = "1.2.0"
    author = "FlaskToolkit Examples"
    category = "示例"
    permission = "user"
    require_framework_version = "4.16.0"  # on_event/emit_event 为 v4.16 BasePlugin 事件集成

    def __init__(self):
        super().__init__()
        # 内存心跳缓冲：{ts, type, message}
        self._heartbeats: List[Dict] = []

    # ---------------- 定时任务声明（核心演示点 1） ----------------
    @property
    def scheduled_tasks(self) -> List[Dict]:
        return [
            # interval 触发器：每 30 秒一次心跳
            {
                "func": self.interval_heartbeat,
                "trigger": "interval",
                "seconds": 30,
                "max_instances": 1,
            },
            # cron 触发器：每分钟整点做一次统计记录
            {
                "func": self.cron_summary,
                "trigger": "cron",
                "minute": "*",
                "max_instances": 1,
            },
        ]

    # ---------------- 定时任务函数 ----------------
    def interval_heartbeat(self):
        """interval 心跳任务：记录心跳 + 发布 heartbeat 自定义事件"""
        self._record("interval", "心跳：框架调度正常运行中")
        self.emit_event('heartbeat', type='interval', message='框架调度正常运行中')
        self.logger.info("scheduler_demo interval 心跳执行")

    def cron_summary(self):
        """cron 统计任务：记录统计 + 发布 stats 自定义事件"""
        count = len(self._load())
        self._record("cron", f"统计快照：当前心跳总数 {count} 条")
        self.emit_event('stats', total=count)
        self.logger.info(f"scheduler_demo cron 统计执行，累计 {count} 条")

    # ---------------- v4.16 事件总线演示（核心演示点 2） ----------------
    def on_load(self):
        """订阅事件：内置全局事件 + 自身自定义事件 + 异步订阅"""
        # 订阅内置全局事件（同步）
        self.on_event('user.login', self._on_user_login)
        self.on_event('plugin.loaded', self._on_plugin_loaded)
        self.on_event('request.finished', self._on_request_finished)
        # 订阅自身发布的自定义事件（event_name 自动加 plugin:scheduler_demo: 前缀）
        self.on_event(self.event_name('heartbeat'), self._on_heartbeat)
        self.on_event(self.event_name('stats'), self._on_stats)
        # 手动发布演示：页面『手动发布事件』发布 manual_trigger，此处订阅并在历史中记录
        self.on_event(self.event_name('manual_trigger'), self._on_manual_trigger)
        # 异步订阅示例：async_=True，后台线程执行，不阻塞事件发布
        self.on_event('plugin.loaded', self._on_plugin_loaded_async, async_=True)

    def _on_user_login(self, event, **data):
        self._record_event(event, data)

    def _on_plugin_loaded(self, event, **data):
        self._record_event(event, data)

    def _on_plugin_loaded_async(self, event, **data):
        self._record_event(event, data, is_async=True)

    def _on_request_finished(self, event, **data):
        self._record_event(event, data)

    def _on_heartbeat(self, event, **data):
        self._record_event(event, data)

    def _on_stats(self, event, **data):
        self._record_event(event, data)

    def _on_manual_trigger(self, event, **data):
        """手动发布事件回调：页面『手动发布事件』发布 manual_trigger 后在此记录，直观展示发布→订阅→记录链路"""
        self._record_event(event, data)

    # ---------------- 数据读写：心跳 + 事件 ----------------
    def _record(self, task_type: str, message: str):
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        entry = {"ts": now, "type": task_type, "message": message}
        data = self._load()
        data.append(entry)
        if len(data) > MAX_HEARTBEATS:
            data = data[-MAX_HEARTBEATS:]
        self._save(data)

    def _load(self) -> List[Dict]:
        return self._read_json(self.heartbeat_file)

    def _save(self, data: List[Dict]):
        self._write_json(self.heartbeat_file, data)

    def _record_event(self, event_name: str, data=None, is_async: bool = False):
        """记录一条事件历史（事件订阅回调落点，验证事件总线链路）"""
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "ts": now,
            "event": event_name,
            "data": json.dumps(data or {}, ensure_ascii=False),
            "async": bool(is_async),
        }
        evs = self._load_events()
        evs.append(entry)
        if len(evs) > MAX_EVENTS:
            evs = evs[-MAX_EVENTS:]
        self._save_events(evs)

    def _load_events(self) -> List[Dict]:
        return self._read_json(self.events_file)

    def _save_events(self, data: List[Dict]):
        self._write_json(self.events_file, data)

    def _clear_events(self):
        self._write_json(self.events_file, [])

    @staticmethod
    def _read_json(path):
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    @staticmethod
    def _write_json(path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @property
    def heartbeat_file(self):
        """心跳持久化文件：get_data_path → plugins/data/scheduler_demo/"""
        return self.get_data_path('heartbeats.json')

    @property
    def events_file(self):
        """事件历史持久化文件"""
        return self.get_data_path('events.json')

    # ---------------- 路由 ----------------
    @property
    def routes(self) -> List[Dict]:
        return [
            {
                "path": "/heartbeats",
                "name": "查询最近心跳记录",
                "methods": ["GET"],
                "params": [
                    {"name": "limit", "type": "number", "required": False, "default": 20, "description": "返回条数"}
                ],
                "view_func": self.get_heartbeats,
            },
            {
                "path": "/stats",
                "name": "任务执行统计",
                "methods": ["GET"],
                "params": [],
                "view_func": self.get_stats,
            },
            {
                "path": "/events",
                "name": "事件总线历史查询",
                "methods": ["GET"],
                "params": [
                    {"name": "limit", "type": "number", "required": False, "default": 20, "description": "返回条数"}
                ],
                "view_func": self.get_events,
            },
            {
                "path": "/events",
                "name": "清空事件总线历史",
                "methods": ["DELETE"],
                "params": [],
                "view_func": self.clear_events,
            },
            {
                "path": "/emit_event",
                "name": "手动发布自定义事件",
                "methods": ["POST"],
                "params": [],
                "view_func": self.emit_event_api,
            },
        ]

    @permission_required("user")
    def get_heartbeats(self):
        """查询最近心跳记录（user 权限）"""
        from flask import request
        limit = int(request.validated_data.get("limit", 20))
        data = self._load()
        return self.success_response(
            data={"total": len(data), "items": data[-limit:]},
            message="心跳记录查询成功",
        )

    @permission_required("user")
    def get_stats(self):
        """任务统计：各类型执行次数 + 调度器状态（user 权限）"""
        data = self._load()
        stats = {"total": len(data)}
        for entry in data:
            t = entry.get("type", "?")
            stats[t] = stats.get(t, 0) + 1

        # 展示调度器状态（来自 global_var.scheduler）
        import global_var
        scheduler = global_var.scheduler
        stats["scheduler_running"] = bool(scheduler and scheduler.running)
        stats["jobs"] = []
        if scheduler:
            for job in scheduler.get_jobs():
                stats["jobs"].append({
                    "id": job.id,
                    "trigger": str(job.trigger),
                    "next_run": str(job.next_run_time or ""),
                })
        return self.success_response(data=stats, message="统计查询成功")

    @permission_required("user")
    def get_events(self):
        """查询事件总线历史（user 权限）"""
        from flask import request
        limit = int(request.validated_data.get("limit", 20))
        data = self._load_events()
        return self.success_response(
            data={"total": len(data), "items": data[-limit:]},
            message="事件历史查询成功",
        )

    @permission_required("admin")
    def clear_events(self):
        """清空事件总线历史（admin 权限）"""
        self._clear_events()
        return self.success_response(message="事件历史已清空")

    @permission_required("user")
    def emit_event_api(self):
        """手动发布一次自定义事件（user 权限），演示 emit_event"""
        from flask import request
        body = request.get_json(silent=True) or {}
        name = (body.get("name") or "manual_trigger").strip()
        self.emit_event(name, manual=True, ts=time.strftime("%Y-%m-%d %H:%M:%S"))
        return self.success_response(
            data={"emitted": f"plugin:scheduler_demo:{name}"},
            message=f"已发布事件 plugin:scheduler_demo:{name}",
        )

    # ---------------- 页面 ----------------
    def page(self):
        data = self._load()
        events = self._load_events()
        return self.render(
            "scheduler_demo.html",
            heartbeats=data[-30:],
            total=len(data),
            events=events[-20:],
        )
