# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""BasePlugin 事件集成 + scheduler_demo 事件总线示例回归（v4.16）

覆盖：
A. BasePlugin 事件助手：
   A1 on_event 订阅后 events.has 生效，且订阅记录进 _event_subs
   A2 emit_event 自动加 plugin:<name>: 前缀
   A3 event_name 返回带前缀的完整事件名
   A4 _cleanup_events 清空本插件订阅（防绑定方法泄漏）
   A5 on_unload 默认调用 _cleanup_events 完成订阅清理
B. scheduler_demo 事件演示：
   B1 on_load 订阅内置全局事件 + 自身自定义事件 + 异步订阅（计数）
   B2 定时任务 interval_heartbeat / cron_summary 发布自定义事件并落盘事件历史
   B3 手动 emit_event（emit_event_api 核心逻辑）发布带前缀事件且被自身订阅记录
   B4 clear_events 清空事件历史
   B5 _cleanup_events 移除订阅后 events.has 全部失效（防泄漏）

运行：python tests/test_plugin_events.py
"""
import json
import os
import sys
import shutil
import tempfile

REAL_BASE = _PROJECT_ROOT
sys.path.insert(0, REAL_BASE)

from core.events import EventBus, events as GLOBAL_EVENTS
from plugins.base_plugin import BasePlugin
from examples.plugins.scheduler_demo.scheduler_demo import SchedulerDemoPlugin
from examples.plugins.dependent_demo.dependent_demo import DependentDemoPlugin

# 隔离环境：新建独立 EventBus，避免污染全局单例（框架运行时不在此测试内加载）
_eb = EventBus()
# 将 core.events.events 替换为隔离实例，让本插件订阅落在隔离总线上
import core.events as _ce
_ce.events = _eb

results = []

def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

def new_demo(tmp):
    """构造 scheduler_demo 实例，数据目录重定向到隔离 tmp。"""
    inst = SchedulerDemoPlugin()
    inst.name = "scheduler_demo"
    def _get_data_path(*sub):
        p = os.path.join(tmp, *sub)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p
    inst.get_data_path = _get_data_path
    return inst

# ============ A：BasePlugin 事件助手 ============
class TestBasePlugin(BasePlugin):
    name = "testbase"
    title = "t"
    description = "d"
    version = "1.0.0"
    category = "测试"
    permission = "user"

    @property
    def routes(self):
        return []


def run_part_a():
    tmp = tempfile.mkdtemp(prefix='ft_a_')
    try:
        inst = TestBasePlugin()

        # A1 on_event 订阅 + _event_subs 记录
        seen = []
        def h(ev, **d):
            seen.append((ev, d))
        inst.on_event('user.login', h)
        check("A1 on_event 订阅生效且记录进 _event_subs",
              _eb.has('user.login') and inst.__dict__.get('_event_subs') == ['user.login'],
              f"_event_subs={inst.__dict__.get('_event_subs')}")
        _eb.emit('user.login', username='admin')
        check("A1b on_event 触发 handler", seen == [('user.login', {'username': 'admin'})], f"seen={seen}")

        # A2 emit_event 自动加前缀
        got = []
        def h2(ev, **d):
            got.append(ev)
        inst.on_event('plugin:testbase:ping', h2)
        inst.emit_event('ping', x=1)
        check("A2 emit_event 自动加 plugin:testbase: 前缀",
              got == ['plugin:testbase:ping'], f"got={got}")

        # A3 event_name
        check("A3 event_name 返回带前缀名",
              inst.event_name('ping') == 'plugin:testbase:ping', inst.event_name('ping'))

        # A4 _cleanup_events 清空订阅
        inst._cleanup_events()
        check("A4 _cleanup_events 清空订阅",
              not _eb.has('user.login') and not _eb.has('plugin:testbase:ping'),
              "残留订阅")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def run_part_c():
    """C：dependent_demo 跨插件事件订阅（v4.16）。"""
    tmp = tempfile.mkdtemp(prefix='ft_c_')
    try:
        inst = DependentDemoPlugin()
        inst.name = "dependent_demo"
        def _gdp(*sub):
            p = os.path.join(tmp, *sub)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            return p
        inst.get_data_path = _gdp
        inst.on_load()
        subs = set(inst.__dict__.get('_event_subs', []))
        expected = {
            'plugin:scheduler_demo:heartbeat', 'plugin:scheduler_demo:stats',
            'plugin:scheduler_demo:manual_trigger', 'user.login', 'user.logout',
            'plugin.loaded', 'request.finished',
        }
        check("C1 dependent_demo 订阅跨插件+全局事件", expected <= subs,
              f"subs={sorted(subs)}")

        # 跨插件事件接收：scheduler_demo 发布 heartbeat → dependent_demo 记录且来源正确归因
        _eb.emit('plugin:scheduler_demo:heartbeat', type='interval', message='x')
        evs = inst._load_events()
        hit = [e for e in evs if e['event'] == 'plugin:scheduler_demo:heartbeat']
        check("C2 收到 scheduler_demo 跨插件事件并记录",
              len(hit) == 1 and hit[0]['source'] == '跨插件(scheduler_demo)',
              f"hit={hit}")

        # 全局事件来源归因
        _eb.emit('user.login', username='admin', user_id=1)
        evs2 = inst._load_events()
        hit2 = [e for e in evs2 if e['event'] == 'user.login']
        check("C3 全局事件来源标记为框架全局",
              len(hit2) == 1 and hit2[0]['source'] == '框架全局',
              f"hit2={hit2}")

        # 清理防泄漏
        inst._cleanup_events()
        for ev in expected:
            check(f"C4 清理后 {ev} 无残留", not _eb.has(ev), "")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_part_b():
    tmp = tempfile.mkdtemp(prefix='ft_b_')
    try:
        inst = new_demo(tmp)
        inst.on_load()
        # B1 订阅：内置3 + 自定义3（heartbeat/stats/manual_trigger）+ 异步1
        expected = [
            'user.login', 'plugin.loaded', 'request.finished',
            'plugin:scheduler_demo:heartbeat', 'plugin:scheduler_demo:stats',
            'plugin:scheduler_demo:manual_trigger',
        ]
        subs = set(inst.__dict__.get('_event_subs', []))
        check("B1 on_load 订阅 5 个事件名", set(expected) == subs, f"subs={sorted(subs)}")
        # 异步订阅同事件 plugin.loaded：其 handler 为绑定方法 → 强引用，events.has 应生效
        check("B1b 异步订阅也已登记", _eb.has('plugin.loaded'), "plugin.loaded 无订阅")

        # B2 定时任务发布自定义事件并落盘
        inst.interval_heartbeat()
        evs = inst._load_events()
        check("B2a interval_heartbeat 发布 heartbeat 事件并被自身订阅记录",
              any(e['event'] == 'plugin:scheduler_demo:heartbeat' for e in evs),
              f"events={[e['event'] for e in evs]}")
        hb = inst._load()
        check("B2b interval_heartbeat 落盘心跳",
              len(hb) >= 1 and hb[-1]['type'] == 'interval', f"hb={len(hb)}")

        inst.cron_summary()
        evs2 = inst._load_events()
        check("B2c cron_summary 发布 stats 事件",
              any(e['event'] == 'plugin:scheduler_demo:stats' for e in evs2),
              f"events={[e['event'] for e in evs2]}")

        # B3 手动 emit_event_api 核心逻辑：emit_event 产出带前缀事件名，且被插件自身 manual_trigger 订阅捕获并记录
        inst.emit_event('manual_trigger', manual=True)
        evs3 = inst._load_events()
        check("B3 emit_event 手动发布带前缀事件且被自身订阅记录",
              any(e['event'] == 'plugin:scheduler_demo:manual_trigger'
                  and json.loads(e['data']).get('manual') is True for e in evs3),
              f"events={[e['event'] for e in evs3]}")

        # B4 clear_events 清空
        inst._clear_events()
        check("B4 clear_events 清空事件历史", inst._load_events() == [], "未清空")

        # B5 _cleanup_events 移除订阅
        inst._cleanup_events()
        for ev in expected:
            check(f"B5 订阅清理后 {ev} 无残留", not _eb.has(ev), "")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

# 主流程：将全局总线指向隔离实例
_ce.events = _eb
run_part_a()
run_part_b()
run_part_c()

# 恢复全局总线（避免影响后续测试）
import core.events as _ce_restore
_ce_restore.events = GLOBAL_EVENTS

passed = sum(1 for _, c, _ in results if c)
print(f"\n==== BasePlugin 事件集成 + scheduler_demo 事件演示（v4.16）：共 {len(results)} 项，通过 {passed}，失败 {len(results) - passed} ====")
sys.exit(0 if passed == len(results) else 1)
