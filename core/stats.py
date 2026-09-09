# -*- coding: utf-8 -*-
"""访问统计：加载、保存、计数（共享状态保存在 global_var，保持同一对象避免引用失效）

v4.14 Statistics 升级：
- 保留 call_stats / frontend_access_stats 累计计数（向后兼容旧 stats.json）；
- 新增 daily_stats 时间桶（按天聚合 count/ok/e4xx/e5xx/延迟），TTL 保留 STATS_RETENTION_DAYS 天；
- 新增 access_profile 访问画像（登录用户记用户名、游客记 IP，设备类型分类），ACCESS_PROFILE_ENABLED 控制。
"""
import json
import logging
import os
from datetime import datetime, date, timedelta

import global_var

logger = logging.getLogger('flask.app')


def classify_device(user_agent: str) -> str:
    """按 UA 轻量分类设备类型：bot / tablet / mobile / desktop（纯字符串匹配，无新依赖）"""
    ua = (user_agent or '').lower()
    if any(k in ua for k in ('bot', 'spider', 'crawl', 'curl', 'python-requests',
                             'httpclient', 'headless', 'java', 'okhttp', 'wget')):
        return 'bot'
    if any(k in ua for k in ('ipad', 'tablet', 'kindle', 'playbook', 'silk', 'nexus 7',
                             'nexus 10', 'xoom', 'galaxy tab')):
        return 'tablet'
    if any(k in ua for k in ('mobile', 'android', 'iphone', 'ipod', 'windows phone',
                             'opera mini', 'blackberry', 'iemobile')):
        return 'mobile'
    return 'desktop'


def _today() -> str:
    return date.today().isoformat()


def _bucket_cell(key: str) -> dict:
    """取当天时间桶中 key 对应的计数字典（不存在则创建）"""
    today = _today()
    day_bucket = global_var.daily_stats.setdefault(today, {})
    cell = day_bucket.get(key)
    if cell is None:
        cell = {'count': 0, 'ok': 0, 'e4xx': 0, 'e5xx': 0, 'ms_sum': 0, 'ms_n': 0}
        day_bucket[key] = cell
    return cell


def record_request_stats(plugin_name, endpoint, status_code, latency_ms,
                         username=None, ip=None, user_agent=None, frontend=False):
    """after_request 聚合入口：写时间桶 + 访问画像。

    plugin_name 为 None 且 frontend=True 时表示前端工具页面访问。
    username 为 None 表示游客（记 IP）；登录用户记用户名并关联 IP。
    """
    key = f"frontend:{endpoint}" if frontend else f"{plugin_name}:{endpoint}"
    cell = _bucket_cell(key)
    cell['count'] += 1
    if 200 <= status_code < 400:
        cell['ok'] += 1
    elif status_code < 500:
        cell['e4xx'] += 1
    else:
        cell['e5xx'] += 1
    if latency_ms >= 0:
        cell['ms_sum'] += latency_ms
        cell['ms_n'] += 1

    # 访问画像（开关控制）
    if not getattr(global_var, 'ACCESS_PROFILE_ENABLED', True):
        return
    if not ip:
        return
    device = classify_device(user_agent)
    now = int(datetime.now().timestamp())
    prof = global_var.access_profile

    # by_ip：IP 为追溯主键（游客与登录用户都记）
    ip_rec = prof['by_ip'].setdefault(ip, {
        'count': 0, 'last_seen': now,
        'devices': {'mobile': 0, 'tablet': 0, 'desktop': 0, 'bot': 0},
        'users': {},
    })
    ip_rec['count'] += 1
    ip_rec['last_seen'] = now
    ip_rec['devices'][device] = ip_rec['devices'].get(device, 0) + 1
    if username:
        ip_rec['users'][username] = ip_rec['users'].get(username, 0) + 1

    # by_user：登录用户汇总（含管理员自己）
    if username:
        u_rec = prof['by_user'].setdefault(username, {
            'count': 0, 'last_seen': now,
            'devices': {'mobile': 0, 'tablet': 0, 'desktop': 0, 'bot': 0},
        })
        u_rec['count'] += 1
        u_rec['last_seen'] = now
        u_rec['devices'][device] = u_rec['devices'].get(device, 0) + 1

    # summary
    prof['summary']['total_visits'] = prof['summary'].get('total_visits', 0) + 1
    prof['summary']['last_seen'] = now
    if not prof['summary'].get('first_seen'):
        prof['summary']['first_seen'] = now


def record_page_view(username=None, ip=None, user_agent=None):
    """插件页面访问：仅更新访问画像（不计 API/前端工具时间桶，避免污染调用统计）"""
    if not getattr(global_var, 'ACCESS_PROFILE_ENABLED', True):
        return
    if not ip:
        return
    device = classify_device(user_agent)
    now = int(datetime.now().timestamp())
    prof = global_var.access_profile
    ip_rec = prof['by_ip'].setdefault(ip, {
        'count': 0, 'last_seen': now,
        'devices': {'mobile': 0, 'tablet': 0, 'desktop': 0, 'bot': 0},
        'users': {},
    })
    ip_rec['count'] += 1
    ip_rec['last_seen'] = now
    ip_rec['devices'][device] = ip_rec['devices'].get(device, 0) + 1
    if username:
        ip_rec['users'][username] = ip_rec['users'].get(username, 0) + 1
    if username:
        u_rec = prof['by_user'].setdefault(username, {
            'count': 0, 'last_seen': now,
            'devices': {'mobile': 0, 'tablet': 0, 'desktop': 0, 'bot': 0},
        })
        u_rec['count'] += 1
        u_rec['last_seen'] = now
        u_rec['devices'][device] = u_rec['devices'].get(device, 0) + 1
    prof['summary']['total_visits'] = prof['summary'].get('total_visits', 0) + 1
    prof['summary']['last_seen'] = now
    if not prof['summary'].get('first_seen'):
        prof['summary']['first_seen'] = now


def cleanup_daily_stats():
    """TTL 清理：删除超过 STATS_RETENTION_DAYS 天的旧时间桶（保留当天）。"""
    try:
        days = int(getattr(global_var, 'STATS_RETENTION_DAYS', 30) or 30)
        if days < 7:
            days = 7
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        stale = [d for d in global_var.daily_stats.keys() if d < cutoff]
        for d in stale:
            del global_var.daily_stats[d]
    except Exception as e:
        logger.error(f"清理统计时间桶失败: {str(e)}", extra={'plugin': 'system'})


def load_stats():
    """加载统计数据（清空并原地回填，保持 global_var 中字典对象不变）"""
    global_var.call_stats.clear()
    global_var.frontend_access_stats.clear()
    global_var.daily_stats.clear()
    global_var.access_profile['by_ip'].clear()
    global_var.access_profile['by_user'].clear()
    global_var.access_profile['summary'].update(
        {'total_visits': 0, 'first_seen': 0, 'last_seen': 0})

    if not os.path.exists(global_var.STATS_FILE):
        save_stats()
        return

    try:
        with open(global_var.STATS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        global_var.call_stats.update(data.get('call_stats', {}))
        global_var.frontend_access_stats.update(data.get('frontend_access_stats', {}))
        global_var.daily_stats.update(data.get('daily_stats', {}))
        prof = data.get('access_profile', {})
        global_var.access_profile['by_ip'].update(prof.get('by_ip', {}))
        global_var.access_profile['by_user'].update(prof.get('by_user', {}))
        global_var.access_profile['summary'].update(prof.get('summary', {}))
        cleanup_daily_stats()
    except Exception as e:
        logger.error(f"加载统计数据失败: {str(e)}", extra={'plugin': 'system'})


def save_stats():
    """保存统计数据到文件"""
    try:
        cleanup_daily_stats()
        data = {
            "call_stats": global_var.call_stats,
            "frontend_access_stats": global_var.frontend_access_stats,
            "daily_stats": global_var.daily_stats,
            "access_profile": global_var.access_profile,
            "last_update": datetime.now().isoformat()
        }
        # 确保数据目录存在（首次启动时 __main__ 尚未执行目录创建）
        os.makedirs(os.path.dirname(global_var.STATS_FILE), exist_ok=True)
        with open(global_var.STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存统计数据失败: {str(e)}", extra={'plugin': 'system'})


def increment_call_stats(plugin_name, endpoint):
    """增加API调用统计（内存中计数，定时批量保存；v4.14 起仅维护累计计数，时间桶/画像走 record_request_stats）"""
    key = f"{plugin_name}:{endpoint}"
    global_var.call_stats[key] = global_var.call_stats.get(key, 0) + 1


def increment_frontend_access(tool_name):
    """增加前端工具访问统计（内存中计数，定时批量保存）"""
    key = f"frontend:{tool_name}"
    global_var.frontend_access_stats[key] = global_var.frontend_access_stats.get(key, 0) + 1


def get_daily_series(days: int = 14) -> list:
    """最近 N 天调用趋势（含无数据的日期，补 0）"""
    days = max(1, min(int(days or 14), 90))
    series = []
    for i in range(days - 1, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        bucket = global_var.daily_stats.get(d, {})
        total = sum(c.get('count', 0) for c in bucket.values())
        ok = sum(c.get('ok', 0) for c in bucket.values())
        e4xx = sum(c.get('e4xx', 0) for c in bucket.values())
        e5xx = sum(c.get('e5xx', 0) for c in bucket.values())
        ms_sum = sum(c.get('ms_sum', 0) for c in bucket.values())
        ms_n = sum(c.get('ms_n', 0) for c in bucket.values())
        series.append({
            'date': d[5:],  # MM-DD
            'count': total, 'ok': ok, 'e4xx': e4xx, 'e5xx': e5xx,
            'avg_ms': round(ms_sum / ms_n, 1) if ms_n else 0,
        })
    return series


def get_error_top(limit: int = 20) -> list:
    """错误最多的接口 Top（4xx/5xx 合计，来自时间桶最近 STATS_RETENTION_DAYS 天）"""
    agg = {}
    for day_bucket in global_var.daily_stats.values():
        for key, cell in day_bucket.items():
            err = cell.get('e4xx', 0) + cell.get('e5xx', 0)
            if err <= 0:
                continue
            rec = agg.setdefault(key, {'count': 0, 'e4xx': 0, 'e5xx': 0})
            rec['count'] += cell.get('count', 0)
            rec['e4xx'] += cell.get('e4xx', 0)
            rec['e5xx'] += cell.get('e5xx', 0)
    rows = [{'key': k, **v} for k, v in agg.items()]
    rows.sort(key=lambda r: r['e4xx'] + r['e5xx'], reverse=True)
    return rows[:max(1, min(limit, 100))]


def get_access_profile_view() -> dict:
    """访问画像聚合视图（供 /api/admin/stats）：用户 Top / IP Top / 设备合计 / 摘要"""
    prof = global_var.access_profile
    users = sorted(prof['by_user'].items(), key=lambda kv: kv[1]['count'], reverse=True)
    ips = sorted(prof['by_ip'].items(), key=lambda kv: kv[1]['count'], reverse=True)
    devices = {'mobile': 0, 'tablet': 0, 'desktop': 0, 'bot': 0}
    for ip_rec in prof['by_ip'].values():
        for dev, n in ip_rec.get('devices', {}).items():
            devices[dev] = devices.get(dev, 0) + n
    return {
        'enabled': getattr(global_var, 'ACCESS_PROFILE_ENABLED', True),
        'summary': prof['summary'],
        'users_top': [{'username': u, 'count': r['count'],
                       'last_seen': r['last_seen'], 'devices': r.get('devices', {})}
                      for u, r in users[:50]],
        'ips_top': [{'ip': ip, 'count': r['count'],
                     'last_seen': r['last_seen'], 'users': list(r.get('users', {}).keys())}
                    for ip, r in ips[:50]],
        'devices': devices,
    }

# ------------------------------ v4.15.4：卸载 / 孤儿统计清理 ------------------------------

def purge_plugin_stats(plugin_name):
    """卸载后端插件后清理其统计残留：call_stats 与 daily_stats 中 ``{plugin}:`` 前缀项。

    返回是否实际删除了数据（供调用方判断是否需 save_stats）。
    """
    prefix = f"{plugin_name}:"
    changed = False
    for k in [k for k in global_var.call_stats if k.startswith(prefix)]:
        del global_var.call_stats[k]
        changed = True
    for day, bucket in global_var.daily_stats.items():
        for k in [k for k in bucket if k.startswith(prefix)]:
            del bucket[k]
            changed = True
    if changed:
        save_stats()
    return changed


def purge_frontend_tool_stats(tool_name):
    """卸载前端工具后清理其统计残留：frontend_access_stats 与 daily_stats 中 ``frontend:{tool}`` 项。

    返回是否实际删除了数据。
    """
    key = f"frontend:{tool_name}"
    changed = False
    if key in global_var.frontend_access_stats:
        del global_var.frontend_access_stats[key]
        changed = True
    for day, bucket in global_var.daily_stats.items():
        if key in bucket:
            del bucket[key]
            changed = True
    if changed:
        save_stats()
    return changed


def purge_orphan_stats():
    """启动孤儿清理：移除已无对应插件/前端工具的统计 key（手动删除文件导致的残留）。

    判定规则：
    - ``frontend:<tool>``：tool 不在已加载 frontend_tools 集合则为孤儿；
    - ``<plugin>:<...>``：冒号前插件名不在已加载 plugins 集合则为孤儿。

    适用于 call_stats / frontend_access_stats / daily_stats。返回删除的 key 总数。
    """
    active_plugins = set(global_var.plugins.keys())
    active_tools = set(t.get('name') for t in global_var.frontend_tools)

    def _is_orphan(key: str) -> bool:
        if key.startswith('frontend:'):
            return key[len('frontend:'):] not in active_tools
        plugin = key.split(':', 1)[0] if ':' in key else key
        return plugin not in active_plugins

    removed = 0
    for k in [k for k in global_var.call_stats if _is_orphan(k)]:
        del global_var.call_stats[k]
        removed += 1
    for k in [k for k in global_var.frontend_access_stats if _is_orphan(k)]:
        del global_var.frontend_access_stats[k]
        removed += 1
    for day, bucket in global_var.daily_stats.items():
        for k in [k for k in bucket if _is_orphan(k)]:
            del bucket[k]
            removed += 1
    if removed:
        save_stats()
    return removed
