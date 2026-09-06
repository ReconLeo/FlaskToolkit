# -*- coding: utf-8 -*-
"""core/ip_watcher.py — v4.11 Reachability M4：局域网 IP 变化检测

解决"非固定 IP 每次都要重新发布访问链接"的痛点：
- 后台线程按 ``IP_WATCH_INTERVAL``（秒，0=关闭）轮询本机局域网 IP
- IP 集合变化时记录 ``last_change_ts`` 与变化详情（旧 → 新），写日志告警，
  网络页读取并提示"检测到 IP 变化，请重新分享访问链接"

设计：轮询逻辑拆分为 ``check_once()`` 便于单测（不依赖真实定时器与网卡）；
线程仅负责周期调用。纯标准库。
"""
import logging
import threading
import time

from core import network

logger = logging.getLogger('flask.app')

# 运行时状态（网络页 GET /api/admin/network 读取）
last_change_ts = None      # 最近一次 IP 变化时间戳（epoch 秒），None=启动后未变化
last_change_detail = None  # 变化详情：{"old": [...], "new": [...]}

_thread = None
_stop_evt = None
_interval = 0
_lock = threading.Lock()


def check_once(current=None):
    """执行一次 IP 变化检查（幂等可重复调用）。

    :param current: 可选注入当前 IP 列表（测试用）；None 时调用 network.get_lan_addresses()
    :return: (changed, old, new) —— changed 表示相对上次快照是否变化
    """
    global last_change_ts, last_change_detail
    if current is None:
        current = network.get_lan_addresses()
    current = list(dict.fromkeys(current))
    with _lock:
        prev = list(dict.fromkeys(getattr(check_once, '_snapshot', [])))
        check_once._snapshot = current
        if not prev:
            # 首次快照不视为变化（避免启动即误报）
            return False, [], current
        if set(prev) != set(current):
            last_change_ts = time.time()
            last_change_detail = {'old': prev, 'new': current}
            logger.warning(f"检测到局域网 IP 变化: {prev} -> {current}"
                           "，请重新分享访问链接（后台『网络与访问』页）",
                           extra={'plugin': 'system'})
            return True, prev, current
        return False, prev, current


def _loop(interval):
    while not _stop_evt.wait(interval):
        try:
            check_once()
        except Exception:
            pass


def start(interval=None):
    """启动 IP 变化检测线程（幂等）。interval<=0 时不启动。"""
    global _thread, _stop_evt, _interval
    interval = interval if interval is not None else int(network.get_ip_watch_interval())
    if interval <= 0:
        return False
    if _thread is not None and _thread.is_alive():
        return True
    _interval = interval
    _stop_evt = threading.Event()
    _thread = threading.Thread(target=_loop, args=(interval,),
                               daemon=True, name='ip-watch')
    _thread.start()
    logger.info(f"IP 变化检测已启动（间隔 {interval} 秒，v4.11）", extra={'plugin': 'system'})
    return True


def stop():
    """停止检测线程（幂等）。"""
    global _thread, _stop_evt
    if _thread is not None and _thread.is_alive():
        _stop_evt.set()
        _thread.join(timeout=2)
    _thread = None
    _stop_evt = None


def get_status():
    """供网络页展示的状态字典。"""
    return {
        'enabled': _interval > 0,
        'interval': _interval,
        'last_change_ts': last_change_ts,
        'last_change_detail': last_change_detail,
    }
