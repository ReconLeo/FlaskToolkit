# -*- coding: utf-8 -*-
"""core/events.py — 轻量进程内事件总线（v4.16 规划）

观察者模式的发布-订阅实现，纯 stdlib、无第三方依赖。用于插件与框架之间的解耦通知：
发布方 ``emit`` 事件，任意订阅方 ``on`` 监听；订阅方之间互不知晓。

- weakref 防泄漏：可 weakref 的 handler（模块级函数等）用弱引用存储，宿主被回收后订阅自动失效；
  不可 weakref 的 handler（绑定方法/闭包）用强引用，可用 ``owner`` 标记便于显式 ``off``。
- 同步为主：``emit`` 默认按 ``priority`` 顺序同步调用全部订阅者。
- 可选异步：``on(async=True)`` 的订阅在后台线程池执行，不阻塞 emit，异常入日志。
- 事件名约定：全局事件用点分命名空间（如 ``plugin.loaded``、``user.login``）；
  插件自定义事件用 ``plugin.<插件名>:<事件名>`` 前缀避免冲突。

用法::

    from core.events import events

    def on_login(**data):
        print('用户登录:', data['username'])

    events.on('user.login', on_login)
    events.emit('user.login', username='admin')
"""
import inspect
import logging
import threading
import weakref
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger('flasktoolkit.events')

# 异步订阅的后台线程池（单例，进程退出自动回收）
_ASYNC_POOL = ThreadPoolExecutor(thread_name_prefix='eventbus', max_workers=4)


class EventBus:
    """进程内事件总线。"""

    def __init__(self):
        self._lock = threading.RLock()
        # event -> [entry]; entry = {ref, handler, once, async, priority, owner}
        self._subs = {}

    # ---------------- 注册 ----------------
    def on(self, event, handler, *, once=False, async_=False, priority=0, owner=None):
        """注册订阅。``handler`` 签名 ``handler(event_name, **data)``。

        ``async_=True`` 时订阅在后台线程池执行（不阻塞 emit）。返回 handler 原引用。
        """
        if not callable(handler):
            raise TypeError('handler must be callable')
        entry = self._make_entry(handler, once, async_, priority, owner)
        with self._lock:
            self._subs.setdefault(event, []).append(entry)
            self._subs[event].sort(key=lambda e: e['priority'])
        return handler

    def once(self, event, handler, **kwargs):
        """只触发一次的订阅，触发后自动移除。"""
        return self.on(event, handler, once=True, **kwargs)

    # ---------------- 取消 ----------------
    def off(self, event, handler=None):
        """取消订阅；``handler`` 为空则清空该事件全部订阅。"""
        with self._lock:
            subs = self._subs.get(event)
            if not subs:
                return
            if handler is None:
                self._subs[event] = []
                return
            self._subs[event] = [e for e in subs if not self._same(e, handler)]

    # ---------------- 触发 ----------------
    def emit(self, event, **data):
        """同步触发事件：按 priority 顺序调用订阅者；weakref 失效订阅自动清理。

        异步订阅（async=True）转入后台线程池执行，不阻塞本调用。
        """
        with self._lock:
            subs = list(self._subs.get(event, []))

        async_entries = []
        for e in subs:
            fn = self._resolve(e)
            if fn is None:
                continue  # weakref 已失效，交由下方统一清理
            if e.get('async'):
                async_entries.append(e)
                continue
            self._invoke(e, fn, event, data)

        # 清理：once 已触发的订阅 + weakref 失效订阅
        self._prune(event, subs)

        # 异步订阅后台执行
        for e in async_entries:
            fn = self._resolve(e)
            if fn is not None:
                _ASYNC_POOL.submit(self._invoke, e, fn, event, data)

    # ---------------- 查询 ----------------
    def has(self, event):
        """该事件是否存在有效订阅（忽略 weakref 已失效者）。"""
        with self._lock:
            subs = self._subs.get(event, [])
        return any(self._resolve(e) is not None for e in subs)

    def clear(self):
        """清空全部订阅。"""
        with self._lock:
            self._subs.clear()

    # ---------------- 内部 ----------------
    @staticmethod
    def _make_entry(handler, once, async_, priority, owner):
        entry = {'ref': None, 'handler': None, 'once': bool(once),
                 'async': bool(async_), 'priority': priority, 'owner': owner}
        if inspect.ismethod(handler):
            # 绑定方法对象 transient：weakref.ref 会立即失效（ref() 返回 None），须强引用
            entry['handler'] = handler
        else:
            try:
                entry['ref'] = weakref.ref(handler)
            except TypeError:
                entry['handler'] = handler  # 闭包等不可 weakref → 强引用
        return entry

    @staticmethod
    def _resolve(e):
        """返回 entry 对应的 callable；weakref 失效返回 None。"""
        if e['handler'] is not None:
            return e['handler']
        ref = e.get('ref')
        return ref() if ref is not None else None

    @staticmethod
    def _same(e, handler):
        """判断 entry 是否对应 handler。"""
        if e['handler'] is handler:
            return True
        ref = e.get('ref')
        if ref is not None:
            try:
                return ref() is handler
            except Exception:
                return False
        return False

    def _invoke(self, e, fn, event, data):
        try:
            fn(event, **data)
        except Exception:
            logger.exception('事件 %s 订阅者执行异常（owner=%s）',
                             event, e.get('owner'))

    def _prune(self, event, subs):
        """移除 once 已触发的订阅与 weakref 失效订阅。"""
        to_remove_ids = set()
        for e in subs:
            if e.get('once'):
                to_remove_ids.add(id(e))
            elif self._resolve(e) is None:
                to_remove_ids.add(id(e))
        if not to_remove_ids:
            return
        with self._lock:
            cur = self._subs.get(event, [])
            self._subs[event] = [e for e in cur if id(e) not in to_remove_ids]


# 全局事件总线单例
events = EventBus()
