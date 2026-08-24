# -*- coding: utf-8 -*-
"""
示例插件：APScheduler 定时任务（scheduler_demo）
==================================================
展示框架的定时任务能力：

1. scheduled_tasks 属性：声明定时任务，框架加载插件时自动注册到 APScheduler。
   - interval 触发器：每 30 秒执行一次心跳
   - cron 触发器：每分钟整点执行一次统计
2. 定时任务写入心跳记录（内存 + 持久化到 data/scheduler_demo.json）。
3. 查询 API 与自定义页面：实时展示任务执行历史与统计。

安装后访问：
- 页面 /plugin/scheduler_demo
- API  /api/scheduler_demo/heartbeats  （最近 N 条心跳，user 权限）
- API  /api/scheduler_demo/stats       （任务统计，user 权限）

说明：scheduled_tasks 中每个任务配置会传给 APScheduler 的 add_job，
     func 会被框架取出作为任务函数，其余 key 作为触发器参数
     （trigger 支持 interval / cron / date，参数与 APScheduler 一致）。
"""
import json
import os
import time
from typing import List, Dict

from global_var import BASE_DIR
from plugins.base_plugin import BasePlugin, permission as permission_required

# 心跳记录文件（运行时数据，不入库）
HEARTBEAT_FILE = os.path.join(BASE_DIR, 'data', 'scheduler_demo.json')

# 心跳最大保留条数
MAX_HEARTBEATS = 200


class SchedulerDemoPlugin(BasePlugin):
    name = "scheduler_demo"
    title = "示例：APScheduler 定时任务"
    description = "定时任务示例：通过 scheduled_tasks 属性声明 interval（间隔）与 cron（表达式）两类触发器，定时写入心跳记录，页面实时展示调度历史。"
    version = "1.0.0"
    author = "FlaskToolkit Examples"
    category = "示例"
    permission = "user"
    require_framework_version = "4.1.0"

    def __init__(self):
        super().__init__()
        # 内存心跳缓冲：{ts, type, message}
        self._heartbeats: List[Dict] = []

    # ---------------- 定时任务声明（核心演示点） ----------------
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
        """interval 心跳任务：每秒/每次记录一条心跳"""
        self._record("interval", "心跳：框架调度正常运行中")
        self.logger.info("scheduler_demo interval 心跳执行")

    def cron_summary(self):
        """cron 统计任务：每分钟记录一次累计统计"""
        count = len(self._load())
        self._record("cron", f"统计快照：当前心跳总数 {count} 条")
        self.logger.info(f"scheduler_demo cron 统计执行，累计 {count} 条")

    # ---------------- 数据读写 ----------------
    def _record(self, task_type: str, message: str):
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        entry = {"ts": now, "type": task_type, "message": message}
        data = self._load()
        data.append(entry)
        # 只保留最近 MAX_HEARTBEATS 条，避免无限增长
        if len(data) > MAX_HEARTBEATS:
            data = data[-MAX_HEARTBEATS:]
        self._save(data)

    def _load(self) -> List[Dict]:
        if not os.path.exists(HEARTBEAT_FILE):
            return []
        try:
            with open(HEARTBEAT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save(self, data: List[Dict]):
        os.makedirs(os.path.dirname(HEARTBEAT_FILE), exist_ok=True)
        with open(HEARTBEAT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

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

    # ---------------- 页面 ----------------
    def page(self):
        from flask import render_template
        data = self._load()
        return render_template(
            "plugins/scheduler_demo.html",
            plugin=self,
            heartbeats=data[-30:],
            total=len(data),
        )
