# -*- coding: utf-8 -*-
"""pc_collect.py — PC 端长稳采集（阶段 3C：12h+ 后台运行）。

采集项（每 60s）：
  - 框架进程 CPU / 内存 RSS / 句柄数 / 线程数（psutil；缺失则仅心跳）
  - data/audit.log 行数与文件大小增长
  - 本机到框架端口的 TCP 连接数（ESTABLISHED / TIME_WAIT 观察）
心跳（每 10min）：登录态请求 /api/admin/system/info，记录状态与耗时，探测服务活性。

用法（Git Bash，后台）：
  python test_server/pc_collect.py --base https://127.0.0.1:5010 --hours 12 &
输出：test_server/diagnostics/longrun_<时间戳>.jsonl

进程发现：--pid 指定；未指定时按命令行包含 app.py 的 python 进程自动匹配。
"""
import argparse
import json
import os
import ssl
import time
import urllib.error
import urllib.request

DEFAULT_USER = 'admin'
DEFAULT_PASS = 'admin123'
DIAG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'diagnostics')
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


def find_framework_pid():
    """按命令行含 app.py 的 python 进程自动匹配。"""
    try:
        import psutil
        for p in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cl = ' '.join(p.info['cmdline'] or [])
                if 'app.py' in cl and 'python' in p.info['name'].lower():
                    return p.info['pid']
            except Exception:
                continue
    except ImportError:
        pass
    return None


def proc_metrics(pid):
    try:
        import psutil
        p = psutil.Process(pid)
        with p.oneshot():
            return {
                'cpu_percent': p.cpu_percent(interval=None) or 0.0,
                'rss_mb': round(p.memory_info().rss / 1024 / 1024, 1),
                'num_handles': len(p.open_files()) + len(p.net_connections()),
                'num_threads': p.num_threads(),
            }
    except Exception:
        return None


def audit_size():
    p = os.path.join(BASE_DIR, 'data', 'audit.log')
    try:
        with open(p, 'rb') as f:
            lines = 0
            for _ in f:
                lines += 1
        return {'audit_lines': lines, 'audit_bytes': os.path.getsize(p)}
    except Exception:
        return None


def conn_counts(port):
    try:
        import psutil
        est = tw = 0
        for c in psutil.net_connections(kind='tcp'):
            try:
                if c.laddr and c.laddr.port == port:
                    if c.status == 'ESTABLISHED':
                        est += 1
                    elif c.status == 'TIME_WAIT':
                        tw += 1
            except Exception:
                continue
        return {'established': est, 'time_wait': tw}
    except Exception:
        return None


def heartbeat(base, user, password, timeout=20):
    """登录态心跳：记录 HTTP 状态与耗时。"""
    t0 = time.time()
    import http.cookiejar
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        urllib.request.HTTPSHandler(context=_CTX))
    try:
        req = urllib.request.Request(base.rstrip('/') + '/api/auth/login',
                                     data=json.dumps({'username': user, 'password': password}).encode(),
                                     headers={'Content-Type': 'application/json'}, method='POST')
        r = opener.open(req, timeout=timeout)
        r.read()
        cookie = '; '.join('%s=%s' % (c.name, c.value) for c in cj)
        req2 = urllib.request.Request(base.rstrip('/') + '/api/admin/system/info',
                                      headers={'Cookie': cookie, 'X-CSRF-Token': _csrf_of(cj)})
        r2 = opener.open(req2, timeout=timeout)
        r2.read()
        return {'ok': True, 'login_status': r.status, 'api_status': r2.status,
                'ms': round((time.time() - t0) * 1000, 1)}
    except urllib.error.HTTPError as e:
        return {'ok': False, 'error': 'HTTP %s' % e.code, 'ms': round((time.time() - t0) * 1000, 1)}
    except Exception as e:
        return {'ok': False, 'error': '%s: %s' % (type(e).__name__, e),
                'ms': round((time.time() - t0) * 1000, 1)}


def _csrf_of(cj):
    for c in cj:
        if c.name == 'csrf_token':
            return c.value
    return ''


def main():
    ap = argparse.ArgumentParser(description='FlaskToolkit 长稳采集')
    ap.add_argument('--base', required=True, help='框架地址，如 https://127.0.0.1:5010')
    ap.add_argument('--hours', type=float, default=12.0)
    ap.add_argument('--pid', type=int, default=None)
    ap.add_argument('--user', default=DEFAULT_USER)
    ap.add_argument('--password', default=DEFAULT_PASS)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    from urllib.parse import urlparse
    port = urlparse(args.base).port or 5000
    pid = args.pid or find_framework_pid()
    print('长稳采集启动：pid=%s base=%s hours=%s' % (pid, args.base, args.hours), flush=True)

    os.makedirs(DIAG_DIR, exist_ok=True)
    ts = time.strftime('%Y%m%d_%H%M%S')
    out = args.out or os.path.join(DIAG_DIR, 'longrun_%s.jsonl' % ts)
    deadline = time.time() + args.hours * 3600
    hb_every = 600.0   # 心跳 10min
    last_hb = 0.0
    start = time.time()
    with open(out, 'w', encoding='utf-8') as f:
        while time.time() < deadline:
            row = {'t': round(time.time() - start, 1), 'clock': time.strftime('%H:%M:%S')}
            pm = proc_metrics(pid) if pid else None
            if pm:
                row.update(pm)
            au = audit_size()
            if au:
                row.update(au)
            cc = conn_counts(port)
            if cc:
                row.update(cc)
            if time.time() - last_hb >= hb_every:
                hb = heartbeat(args.base, args.user, args.password)
                row['heartbeat'] = hb
                last_hb = time.time()
                print('t=%.0fs heartbeat=%s' % (row['t'], hb.get('ok')), flush=True)
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
            f.flush()
            time.sleep(60)
    print('长稳采集结束，共 %.0f min，输出 %s' % ((time.time() - start) / 60, out), flush=True)


if __name__ == '__main__':
    main()
