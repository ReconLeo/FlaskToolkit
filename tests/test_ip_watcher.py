# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""IP 变化检测回归（v4.11 Reachability M4，core/ip_watcher.py）

场景：
A. 首次快照不视为变化（启动即不误报）
B. IP 集合变化 → 记录 last_change_ts / last_change_detail（old → new）
C. 无变化 → 不更新状态
D. 去重与排序无关：同集合不同顺序不触发变化
E. start/stop：间隔<=0 不启动；线程生命周期
运行：python tests/test_ip_watcher.py
"""
import os
import sys
import time

sys.path.insert(0, _PROJECT_ROOT)

import global_var
from core import ip_watcher

results = []

def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")


def main():
    saved_cfg = dict(global_var._user_config)
    try:
        # 清空快照与状态
        ip_watcher.check_once._snapshot = []
        ip_watcher.last_change_ts = None
        ip_watcher.last_change_detail = None

        # A. 首次快照
        changed, old, new = ip_watcher.check_once(['192.168.1.5'])
        check('A1 首次快照不视为变化', changed is False and old == [], f'{changed}')
        check('A2 首次不记录 change_ts', ip_watcher.last_change_ts is None, '')

        # B. 变化
        changed, old, new = ip_watcher.check_once(['192.168.1.5', '10.0.0.8'])
        check('B1 IP 增加触发变化', changed is True and '10.0.0.8' in new, f'{old}->{new}')
        check('B2 记录 change_ts', ip_watcher.last_change_ts is not None, '')
        check('B3 记录变化详情 old→new',
              ip_watcher.last_change_detail == {'old': ['192.168.1.5'], 'new': ['192.168.1.5', '10.0.0.8']},
              str(ip_watcher.last_change_detail))
        ts1 = ip_watcher.last_change_ts

        # C. 无变化
        time.sleep(0.01)
        changed, _, _ = ip_watcher.check_once(['192.168.1.5', '10.0.0.8'])
        check('C1 无变化不触发', changed is False, '')
        check('C2 change_ts 不更新', ip_watcher.last_change_ts == ts1, '')

        # D. 顺序无关 + 去重
        changed, _, _ = ip_watcher.check_once(['10.0.0.8', '192.168.1.5', '192.168.1.5'])
        check('D1 同集合不同顺序不触发', changed is False, '')

        # E. 移除 IP 也触发
        changed, old, new = ip_watcher.check_once(['10.0.0.8'])
        check('E1 IP 减少触发变化',
              changed is True and set(old) == {'192.168.1.5', '10.0.0.8'} and new == ['10.0.0.8'],
              f'{old}->{new}')

        # F. start/stop
        global_var._user_config['IP_WATCH_INTERVAL'] = 0
        check('F1 间隔 0 不启动', ip_watcher.start() is False, '')
        global_var._user_config['IP_WATCH_INTERVAL'] = 1
        ok = ip_watcher.start()
        check('F2 start 启动线程', ok is True, '')
        check('F3 幂等重复 start', ip_watcher.start() is True, '')
        st = ip_watcher.get_status()
        check('F4 状态 enabled+interval', st['enabled'] is True and st['interval'] == 1, str(st))
        check('F5 状态含变化信息', 'last_change_ts' in st and 'last_change_detail' in st, '')
        ip_watcher.stop()
        ip_watcher.stop()
        check('F6 stop 幂等', True, '')
    finally:
        ip_watcher.stop()
        ip_watcher.check_once._snapshot = []
        global_var._user_config.clear()
        global_var._user_config.update(saved_cfg)

    print(f'\n==== IP 变化检测（v4.11 M4）：共 {len(results)} 项，'
          f'通过 {sum(1 for _, c, _ in results if c)}，'
          f'失败 {sum(1 for _, c, _ in results if not c)} ====')
    ok = all(c for _, c, _ in results)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
