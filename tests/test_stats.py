# -*- coding: utf-8 -*-
"""v4.14 Statistics 回归：设备分类 / 时间桶聚合（count/ok/4xx/5xx/延迟）/ 访问画像（登录用户记身份、游客记 IP）/
TTL 清理 / 趋势序列 / 错误 Top / 画像视图 / 开关控制 / 新旧 stats.json 兼容"""
import io
import json
import os
import sys
import tempfile
import time
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import global_var
from core import stats as stats_mod

_PASS = 0
_FAIL = 0

def check(name, cond, debug=''):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  ✓ {name}")
    else:
        _FAIL += 1
        print(f"  ✗ {name}{' | ' + str(debug) if debug else ''}")

# ---------- 隔离环境：monkeypatch STATS_FILE 到临时目录 ----------
_tmp = tempfile.mkdtemp(prefix='ftk_stats_')
_orig_stats_file = global_var.STATS_FILE
_orig_profile_enabled = getattr(global_var, 'ACCESS_PROFILE_ENABLED', True)
_orig_retention = getattr(global_var, 'STATS_RETENTION_DAYS', 30)
global_var.STATS_FILE = os.path.join(_tmp, 'stats.json')
global_var.ACCESS_PROFILE_ENABLED = True
global_var.STATS_RETENTION_DAYS = 30

# 重置共享状态
global_var.call_stats.clear()
global_var.frontend_access_stats.clear()
global_var.daily_stats.clear()
global_var.access_profile['by_ip'].clear()
global_var.access_profile['by_user'].clear()
global_var.access_profile['summary'].update({'total_visits': 0, 'first_seen': 0, 'last_seen': 0})

# ---------- 1. 设备分类 ----------
print('== 1. classify_device ==')
check('bot: curl', stats_mod.classify_device('curl/8.0') == 'bot')
check('bot: python-requests', stats_mod.classify_device('python-requests/2.31.0') == 'bot')
check('bot: googlebot', stats_mod.classify_device('Mozilla/5.0 (compatible; Googlebot/2.1)') == 'bot')
check('tablet: iPad', stats_mod.classify_device('Mozilla/5.0 (iPad; CPU OS 17_0) AppleWebKit/605.1.15') == 'tablet')
check('tablet: Kindle', stats_mod.classify_device('Mozilla/5.0 (Kindle/3.0)') == 'tablet')
check('mobile: iPhone', stats_mod.classify_device('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Mobile Safari') == 'mobile')
check('mobile: Android', stats_mod.classify_device('Mozilla/5.0 (Linux; Android 14; Pixel 8) Mobile') == 'mobile')
check('desktop: Chrome Win', stats_mod.classify_device('Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0 Safari/537.36') == 'desktop')
check('desktop: 空 UA', stats_mod.classify_device('') == 'desktop')

# ---------- 2. 时间桶聚合 ----------
print('== 2. daily_stats 时间桶 ==')
_today = date.today().isoformat()
stats_mod.record_request_stats('demo', '/hello', 200, 15.0, username='admin', ip='192.168.1.10', user_agent='Mozilla/5.0 (Windows NT 10.0) Chrome')
stats_mod.record_request_stats('demo', '/hello', 200, 25.0, username='admin', ip='192.168.1.10', user_agent='Mozilla/5.0 (Windows NT 10.0) Chrome')
stats_mod.record_request_stats('demo', '/hello', 404, 8.0, username=None, ip='192.168.1.11', user_agent='curl/8.0')
stats_mod.record_request_stats('demo', '/hello', 500, 30.0, username='admin', ip='192.168.1.10', user_agent='Mozilla/5.0 (Windows NT 10.0) Chrome')
stats_mod.record_request_stats(None, 'password_generator', 200, 5.0, username='admin', ip='192.168.1.10', user_agent='Mozilla/5.0 (Windows NT 10.0) Chrome', frontend=True)

_bucket = global_var.daily_stats.get(_today, {})
cell = _bucket.get('demo:/hello', {})
check('API 聚合 count=4', cell.get('count') == 4, cell)
check('API 聚合 ok=2', cell.get('ok') == 2, cell)
check('API 聚合 e4xx=1', cell.get('e4xx') == 1, cell)
check('API 聚合 e5xx=1', cell.get('e5xx') == 1, cell)
check('API 聚合 ms_sum=78', cell.get('ms_sum') == 78, cell)
check('API 聚合 ms_n=4', cell.get('ms_n') == 4, cell)
fcell = _bucket.get('frontend:password_generator', {})
check('前端工具桶 count=1', fcell.get('count') == 1, fcell)
check('累计计数不受影响（call_stats 未写）', global_var.call_stats.get('demo:/hello') is None)

# ---------- 3. 访问画像 ----------
print('== 3. access_profile 画像 ==')
by_ip = global_var.access_profile['by_ip']
check('by_ip 记录登录用户 IP', '192.168.1.10' in by_ip, list(by_ip.keys()))
check('by_ip count=4（3 API + 1 前端）', by_ip['192.168.1.10']['count'] == 4, by_ip['192.168.1.10'])
check('by_ip 关联用户名 admin（3 API + 1 前端）', by_ip['192.168.1.10']['users'].get('admin') == 4, by_ip['192.168.1.10'])
check('by_ip 游客单独记录', '192.168.1.11' in by_ip)
check('游客 IP 无 users 关联', by_ip['192.168.1.11'].get('users', {}) == {})
by_user = global_var.access_profile['by_user']
check('by_user 记 admin', 'admin' in by_user, list(by_user.keys()))
check('by_user count=4（3 API + 1 前端）', by_user['admin']['count'] == 4, by_user['admin'])
check('游客不进 by_user', 'unknown' not in by_user)
check('by_ip 设备分类 desktop（3 API + 1 前端）', by_ip['192.168.1.10']['devices'].get('desktop') == 4)
check('by_ip 游客设备 bot', by_ip['192.168.1.11']['devices'].get('bot') == 1)
check('summary total_visits=5', global_var.access_profile['summary'].get('total_visits') == 5,
      global_var.access_profile['summary'])
check('summary last_seen 有值', bool(global_var.access_profile['summary'].get('last_seen')))

# ---------- 4. 页面访问只画像 ----------
print('== 4. record_page_view ==')
_nb_before = len(global_var.daily_stats.get(_today, {}))
stats_mod.record_page_view(username='admin', ip='192.168.1.10', user_agent='Mozilla/5.0 (iPhone) Mobile')
check('页面访问不写时间桶', len(global_var.daily_stats.get(_today, {})) == _nb_before)
check('页面访问计画像 by_user', global_var.access_profile['by_user']['admin']['count'] == 5)
check('页面访问设备 mobile', global_var.access_profile['by_user']['admin']['devices'].get('mobile') == 1)

# ---------- 5. TTL 清理 ----------
print('== 5. cleanup_daily_stats TTL ==')
_old_day = (date.today() - timedelta(days=31)).isoformat()
_old_day2 = (date.today() - timedelta(days=3)).isoformat()
global_var.daily_stats.setdefault(_old_day, {'demo:/old': {'count': 9, 'ok': 9, 'e4xx': 0, 'e5xx': 0, 'ms_sum': 0, 'ms_n': 0}})
global_var.daily_stats.setdefault(_old_day2, {'demo:/recent': {'count': 1, 'ok': 1, 'e4xx': 0, 'e5xx': 0, 'ms_sum': 0, 'ms_n': 0}})
stats_mod.cleanup_daily_stats()
check('31 天前旧桶被清理', _old_day not in global_var.daily_stats)
check('30 天内桶保留', _old_day2 in global_var.daily_stats)
check('今天桶保留', _today in global_var.daily_stats)

# ---------- 6. 趋势序列 ----------
print('== 6. get_daily_series ==')
series = stats_mod.get_daily_series(14)
check('序列长度 14', len(series) == 14)
check('序列今天有调用', series[-1]['count'] > 0, series[-1])
check('无数据日期补 0', series[0]['count'] == 0, series[0])
check('序列含错误列', series[-1]['e4xx'] >= 1 and series[-1]['e5xx'] >= 1, series[-1])
check('avg_ms 计算正确', series[-1]['avg_ms'] == 16.6, series[-1]['avg_ms'])  # (15+25+8+30+5)/5=16.6（含前端工具延迟）

# ---------- 7. 错误 Top ----------
print('== 7. get_error_top ==')
_etoday = date.today().isoformat()
global_var.daily_stats.setdefault(_etoday, {})['auth:/bad'] = {'count': 10, 'ok': 5, 'e4xx': 5, 'e5xx': 0, 'ms_sum': 0, 'ms_n': 0}
top = stats_mod.get_error_top(5)
check('错误 Top 含 demo:/hello', any(r['key'] == 'demo:/hello' for r in top), top)
check('错误 Top 含 auth:/bad', any(r['key'] == 'auth:/bad' for r in top))
check('错误 Top 排序（最多在前）', top and (top[0]['e4xx'] + top[0]['e5xx']) >= (top[-1]['e4xx'] + top[-1]['e5xx']))
check('错误 Top 限制数量', len(stats_mod.get_error_top(2)) <= 2)

# ---------- 8. 画像视图 ----------
print('== 8. get_access_profile_view ==')
view = stats_mod.get_access_profile_view()
check('视图 enabled=True', view['enabled'] is True)
check('用户 Top 含 admin', any(u['username'] == 'admin' for u in view['users_top']), view['users_top'])
check('IP Top 含 192.168.1.10', any(u['ip'] == '192.168.1.10' for u in view['ips_top']))
check('设备合计非零', sum(view['devices'].values()) > 0, view['devices'])

# ---------- 9. 开关控制 ----------
print('== 9. ACCESS_PROFILE_ENABLED=False ==')
global_var.ACCESS_PROFILE_ENABLED = False
_before_visits = global_var.access_profile['summary'].get('total_visits', 0)
stats_mod.record_request_stats('demo', '/off', 200, 1.0, username='admin', ip='10.0.0.9', user_agent='Mozilla/5.0')
check('关闭后画像不计数', global_var.access_profile['summary'].get('total_visits') == _before_visits)
check('关闭后桶仍记录', global_var.daily_stats.get(_today, {}).get('demo:/off', {}).get('count') == 1)
global_var.ACCESS_PROFILE_ENABLED = _orig_profile_enabled

# ---------- 10. 保存/加载往返与旧文件兼容 ----------
print('== 10. save/load 往返与兼容 ==')
stats_mod.save_stats()
with io.open(global_var.STATS_FILE, encoding='utf-8') as f:
    saved = json.load(f)
check('保存含 daily_stats', 'daily_stats' in saved)
check('保存含 access_profile', 'access_profile' in saved)
check('保存含累计计数', 'call_stats' in saved)
# 旧版文件（无新域）兼容加载
_old = {'call_stats': {'demo:/old': 5}, 'frontend_access_stats': {}, 'last_update': '2026-01-01T00:00:00'}
with io.open(global_var.STATS_FILE, 'w', encoding='utf-8') as f:
    json.dump(_old, f, ensure_ascii=False)
global_var.daily_stats.clear()
global_var.access_profile['by_ip'].clear()
global_var.access_profile['by_user'].clear()
global_var.access_profile['summary'].update({'total_visits': 0, 'first_seen': 0, 'last_seen': 0})
stats_mod.load_stats()
check('旧文件加载累计计数', global_var.call_stats.get('demo:/old') == 5)
check('旧文件加载新域为空不报错', global_var.daily_stats == {} and global_var.access_profile['by_ip'] == {})

# ---------- 收尾 ----------
global_var.STATS_FILE = _orig_stats_file
global_var.ACCESS_PROFILE_ENABLED = _orig_profile_enabled
global_var.STATS_RETENTION_DAYS = _orig_retention

print(f"\n==== 共 {_PASS + _FAIL} 项，通过 {_PASS}，失败 {_FAIL} ====")
sys.exit(1 if _FAIL else 0)
