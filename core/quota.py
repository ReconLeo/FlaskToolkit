# -*- coding: utf-8 -*-
"""core/quota.py — v4.9.1 插件存储配额（capabilities 声明模型）

配额来源优先级（v4.9.1）：
    插件 capabilities ``storage:limit:<size>`` 声明 > 全局单插件默认
    （``PLUGIN_DATA_LIMIT_MB``）> 0（无限制）。

作用目录（配额目录推导）：
    - ``plugins/data/<name>/`` 与 ``plugins/temp/<name>/``（自属，始终计入）
    - 插件 ``filesystem:write`` 声明的外部路径（如 AirDrop 的 ``uploads/``）

v4.9.2 衔接铺垫（本模块预留扩展点，界面/配置项下轮接入）：
    - ``check_upload`` 预留 ``global_limit_mb`` 参数（全局总量配额，0/None=不启用；
      4.9.2 接线 ``PLUGIN_DATA_TOTAL_LIMIT_MB``）
    - ``all_plugins_quota()`` 批量接口（4.9.2 后台"插件空间管理"页按插件列配额/用量/剩余）
"""
import os
import time

import global_var
from core import capabilities as caps_mod

# 目录总量缓存（TTL 秒），避免每次写事件/预检全量 os.walk
_DATA_CACHE_TTL = 5.0
_data_dir_cache = {}          # plugin -> (checked_ts, size_bytes)
_total_cache = None           # (checked_ts, size_bytes) 全局总量缓存（4.9.2 铺垫）


# ------------------------------ 目录与用量 ------------------------------

def _plugin_quota_dirs(plugin):
    """插件配额作用目录：data/temp 自属目录 + filesystem:write 声明的外部路径。"""
    base = os.path.join(global_var.BASE_DIR, 'plugins')
    dirs = [os.path.join(base, 'data', str(plugin)),
            os.path.join(base, 'temp', str(plugin))]
    for d in caps_mod.get_write_dirs(plugin):
        dn = caps_mod._norm_path(d)
        if not any(caps_mod._norm_path(x) == dn for x in dirs):
            dirs.append(d)
    return dirs


def _quota_usage(plugin):
    """插件配额目录总大小（字节，TTL 缓存）。"""
    now = time.time()
    hit = _data_dir_cache.get(str(plugin))
    if hit and now - hit[0] < _DATA_CACHE_TTL:
        return hit[1]
    total = 0
    for d in _plugin_quota_dirs(str(plugin)):
        if os.path.isdir(d):
            for root, _ds, fs in os.walk(d):
                for fn in fs:
                    try:
                        total += os.path.getsize(os.path.join(root, fn))
                    except OSError:
                        pass
    _data_dir_cache[str(plugin)] = (now, total)
    return total


def _total_usage():
    """所有插件数据目录总用量（4.9.2 全局总量配额用，TTL 缓存）。"""
    global _total_cache
    now = time.time()
    if _total_cache and now - _total_cache[0] < _DATA_CACHE_TTL:
        return _total_cache[1]
    total = 0
    base = os.path.join(global_var.BASE_DIR, 'plugins')
    for sub in ('data', 'temp'):
        d = os.path.join(base, sub)
        if os.path.isdir(d):
            for root, _ds, fs in os.walk(d):
                for fn in fs:
                    try:
                        total += os.path.getsize(os.path.join(root, fn))
                    except OSError:
                        pass
    _total_cache = (now, total)
    return total


def invalidate_cache(plugin=None):
    """清配额缓存（安装/卸载/重置后调用）。"""
    if plugin is None:
        _data_dir_cache.clear()
        global _total_cache
        _total_cache = None
    else:
        _data_dir_cache.pop(str(plugin), None)


# ------------------------------ 限额解析 ------------------------------

def data_limit_mb(plugin):
    """插件配额（MB）；0 = 无限制。

    优先级：插件 capabilities storage:limit 声明 > 全局 PLUGIN_DATA_LIMIT_MB。
    plugin 为 None 时仅返回全局默认（审计/预检兼容路径）。
    """
    if plugin is not None:
        declared = caps_mod.get_storage_limit_mb(str(plugin))
        if declared is not None:
            return declared
    try:
        v = global_var.get_user_config().get('PLUGIN_DATA_LIMIT_MB', 50)
        return float(v or 0)
    except Exception:
        return 50.0


def get_plugin_quota(plugin):
    """返回 (limit_mb, usage_mb)；limit 0 = 无限制。"""
    return data_limit_mb(plugin), _quota_usage(plugin) / 1048576


def _in_quota_area(plugin, target):
    """target 是否落在插件配额作用目录（归一化前缀匹配，与 capabilities 同规则）。"""
    tn = caps_mod._norm_path(target)
    for d in _plugin_quota_dirs(str(plugin)):
        dn = caps_mod._norm_path(d)
        if tn == dn or tn.startswith(dn + '/'):
            return True
    return False


# ------------------------------ 预检与批量（供插件 API / 4.9.2 后台） ------------------------------

def check_upload(plugin, new_size_bytes, global_limit_mb=None):
    """上传预检（插件上传 API 写文件前调用）：返回 dict。

    - ``plugin_quota_exceeded``：单插件配额超限（现有用量 + 新文件大小 > 限额）
    - ``global_quota_exceeded``：全局总量超限（4.9.2 接线 global_limit_mb 后生效）
    - ``ok``：放行
    返回：{'ok', 'limit_mb', 'usage_mb', 'remaining_mb', 'reason'}
    """
    plugin = str(plugin)
    limit_mb = data_limit_mb(plugin)
    usage_bytes = _quota_usage(plugin)
    usage_mb = usage_bytes / 1048576
    remaining_mb = 0.0 if not limit_mb else max(0.0, limit_mb - usage_mb)
    if limit_mb and (usage_bytes + int(new_size_bytes)) > int(limit_mb * 1048576):
        return {'ok': False, 'limit_mb': limit_mb, 'usage_mb': usage_mb,
                'remaining_mb': remaining_mb, 'reason': 'plugin_quota_exceeded'}
    if global_limit_mb:
        total_bytes = _total_usage()
        if (total_bytes + int(new_size_bytes)) > int(global_limit_mb * 1048576):
            return {'ok': False, 'limit_mb': global_limit_mb, 'usage_mb': total_bytes / 1048576,
                    'remaining_mb': max(0.0, global_limit_mb - total_bytes / 1048576),
                    'reason': 'global_quota_exceeded'}
    return {'ok': True, 'limit_mb': limit_mb, 'usage_mb': usage_mb,
            'remaining_mb': remaining_mb, 'reason': 'ok'}


def all_plugins_quota():
    """按插件批量配额信息（4.9.2 后台"插件空间管理"页铺垫）。"""
    out = []
    base = os.path.join(global_var.BASE_DIR, 'plugins', 'data')
    if os.path.isdir(base):
        for n in sorted(os.listdir(base)):
            d = os.path.join(base, n)
            if os.path.isdir(d):
                limit, usage = get_plugin_quota(n)
                out.append({'plugin': n, 'limit_mb': limit, 'usage_mb': usage,
                            'remaining_mb': None if not limit else max(0.0, limit - usage)})
    return out
