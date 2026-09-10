# -*- coding: utf-8 -*-
"""test_events.py — core/events.py 事件总线单元测试

覆盖：注册/触发/priority 排序/once 自动移除/off 取消/weakref 失效清理/
绑定方法强引用/异步后台执行/has/clear/内置事件埋点触发。

可直接 `python tests/test_events.py` 运行（assert 风格，无 pytest 依赖）。
"""
import gc
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.events import EventBus, events


def test_priority_order():
    eb = EventBus()
    order = []

    def h0(ev, **d):
        order.append('p0')

    def h5(ev, **d):
        order.append('p5')

    def h2(ev, **d):
        order.append('p2')

    eb.on('e', h5, priority=5)
    eb.on('e', h0, priority=0)
    eb.on('e', h2, priority=2)
    eb.emit('e')
    assert order == ['p0', 'p2', 'p5'], order


def test_data_passing():
    eb = EventBus()
    got = {}

    def h(ev, **d):
        got.update(d)
        assert ev == 'e'

    eb.on('e', h)
    eb.emit('e', username='admin', role='admin')
    assert got == {'username': 'admin', 'role': 'admin'}, got


def test_once():
    eb = EventBus()
    calls = {'n': 0}

    def h(ev, **d):
        calls['n'] += 1

    eb.once('e', h)
    eb.emit('e')
    eb.emit('e')
    assert calls['n'] == 1, calls


def test_off():
    eb = EventBus()
    calls = {'n': 0}

    def h(ev, **d):
        calls['n'] += 1

    eb.on('e', h)
    eb.off('e', h)
    eb.emit('e')
    assert calls['n'] == 0, calls
    assert not eb.has('e')


def test_off_clear_all():
    eb = EventBus()
    seen = []

    def h1(ev, **d):
        seen.append('h1')

    def h2(ev, **d):
        seen.append('h2')

    eb.on('e', h1)
    eb.on('e', h2)
    eb.off('e')  # 清空该事件全部
    eb.emit('e')
    assert seen == [], seen


def test_weakref_collect():
    eb = EventBus()

    class Owner:
        pass

    owner = Owner()

    def h(ev, **d):
        pass

    eb.on('e', h, owner=owner)
    assert eb.has('e')
    del owner, h
    gc.collect()
    eb.emit('e')  # 触发失效清理
    assert not eb.has('e'), 'weakref 失效订阅未被清理'


def test_bound_method_strong_ref():
    eb = EventBus()

    class M:
        def handle(self, ev, **d):
            pass

    m = M()
    eb.on('e', m.handle, owner=m)
    assert eb.has('e')
    eb.off('e')  # 绑定方法用清空事件方式取消
    assert not eb.has('e')


def test_async_nonblocking():
    eb = EventBus()
    done = []

    def h(ev, **d):
        time.sleep(0.15)
        done.append(ev)

    eb.on('e', h, async_=True)
    t0 = time.time()
    eb.emit('e')
    assert done == [], '异步订阅不应阻塞 emit'
    assert time.time() - t0 < 0.1, 'emit 被异步订阅阻塞'
    time.sleep(0.3)
    assert done == ['e'], done


def test_has_and_clear():
    eb = EventBus()

    def h(ev, **d):
        pass

    assert not eb.has('e')
    eb.on('e', h)
    assert eb.has('e')
    eb.clear()
    assert not eb.has('e')


def test_exception_isolation():
    """订阅者抛异常不影响其他订阅者。"""
    eb = EventBus()
    seen = []

    def bad(ev, **d):
        raise RuntimeError('boom')

    def good(ev, **d):
        seen.append(ev)

    eb.on('e', bad)
    eb.on('e', good)
    eb.emit('e')
    assert seen == ['e'], seen


def test_builtin_event_emission():
    """内置事件能通过全局总线发出（埋点接线正确）。"""
    got = []

    def h(ev, **d):
        got.append((ev, d.get('plugin_name')))

    events.on('plugin.loaded', h)
    events.emit('plugin.loaded', plugin_name='demo')
    events.off('plugin.loaded', h)
    assert ('plugin.loaded', 'demo') in got, got


def run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f'PASS {fn.__name__}')
            passed += 1
        except AssertionError as e:
            print(f'FAIL {fn.__name__}: {e}')
        except Exception as e:
            print(f'ERROR {fn.__name__}: {type(e).__name__}: {e}')
    print(f'\n通过 {passed}/{len(fns)}')
    return 0 if passed == len(fns) else 1


if __name__ == '__main__':
    sys.exit(run())
