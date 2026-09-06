# -*- coding: utf-8 -*-
"""pc_stress.py — PC 端 FlaskToolkit 并发/大文件压测（标准库 urllib + threading）。

场景：
  mixed   登录态混合 API 并发（system/info + network + 首页 + 静态资源），统计延迟分布；
  login   并发登录（验证 ip_username 锁定在并发下是否误伤正常登录）；
  upload  并发上传无效 zip（2MB × N，观察上传链路并发排队与 413/校验行为，不污染插件目录）。

HTTPS 自签名：ssl 上下文不校验证书（仅测试）。
threaded 对比：服务器端以 FT_THREADED=1 环境变量启动框架（临时开关，默认单线程），
              同一压测命令分别在两种模式下运行即可对比。

用法（Git Bash）：
  python test_server/pc_stress.py --base https://127.0.0.1:5010 --scenario mixed --concurrency 100 --rounds 3
  python test_server/pc_stress.py --base https://127.0.0.1:5010 --scenario login --concurrency 50
  python test_server/pc_stress.py --base https://127.0.0.1:5010 --scenario upload --concurrency 10
"""
import argparse
import json
import os
import ssl
import statistics
import threading
import time
import urllib.error
import urllib.request
import uuid

DEFAULT_USER = 'admin'
DEFAULT_PASS = 'admin123'
DIAG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'diagnostics')

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


def log(msg):
    print('[pc_stress] %s' % msg, flush=True)


class HttpClient:
    """极简 cookie 会话（token/csrf_token 均为 Set-Cookie）。"""

    def __init__(self, base, timeout=30):
        self.base = base.rstrip('/')
        self.timeout = timeout
        self.cookies = {}

    def _grab_cookies(self, resp):
        for h, v in resp.headers.items():
            if h.lower() == 'set-cookie':
                pair = v.split(';', 1)[0]
                if '=' in pair:
                    k, val = pair.split('=', 1)
                    self.cookies[k] = val

    def request(self, method, path, data=None, headers=None, timeout=None, raw_body=None, content_type=None):
        url = self.base + path
        req_headers = dict(headers or {})
        cookie_str = '; '.join('%s=%s' % (k, v) for k, v in self.cookies.items())
        if cookie_str:
            req_headers['Cookie'] = cookie_str
        body = None
        if raw_body is not None:
            body = raw_body
        elif data is not None:
            body = json.dumps(data).encode('utf-8')
            req_headers.setdefault('Content-Type', 'application/json')
        elif content_type and body is None:
            body = b''
            req_headers['Content-Type'] = content_type
        req = urllib.request.Request(url, data=body, method=method, headers=req_headers)
        try:
            resp = urllib.request.urlopen(req, timeout=timeout or self.timeout, context=_CTX)
            self._grab_cookies(resp)
            raw = resp.read()
            return resp.status, raw
        except urllib.error.HTTPError as e:
            self._grab_cookies(e)
            return e.code, e.read()
        except Exception as e:
            raise

    def get(self, path, timeout=None):
        return self.request('GET', path, timeout=timeout)

    def post_json(self, path, data, timeout=None):
        return self.request('POST', path, data=data, timeout=timeout)

    @property
    def csrf(self):
        return self.cookies.get('csrf_token', '')


def login(c, user=DEFAULT_USER, password=DEFAULT_PASS):
    code, raw = c.post_json('/api/auth/login', {'username': user, 'password': password})
    try:
        body = json.loads(raw.decode('utf-8', 'replace'))
    except Exception:
        body = {}
    return code, body


def scenario_mixed(base, concurrency, rounds):
    log('场景 mixed：%d 并发 × %d 轮' % (concurrency, rounds))
    c = HttpClient(base)
    code, body = login(c)
    if code != 200 or body.get('code') not in (0, 200, None):
        log('登录失败：HTTP %s %s' % (code, body))
        return {'error': 'login failed'}
    hdr = {'X-CSRF-Token': c.csrf}
    paths = ['/api/admin/system/info', '/api/admin/network', '/',
             '/static/css/style.css', '/api/auth/user/info']

    def one(path):
        t0 = time.time()
        try:
            code2, _ = c.get(path, timeout=60)
            return code2, (time.time() - t0) * 1000, None
        except Exception as e:
            return None, (time.time() - t0) * 1000, '%s: %s' % (type(e).__name__, e)

    lat, errs, statuses, wall0 = [], [], {}, time.time()
    for rnd in range(1, rounds + 1):
        threads, res = [], []
        lock = threading.Lock()
        def worker():
            r = one(paths[uuid.uuid4().int % len(paths)])
            with lock:
                res.append(r)
        for _ in range(concurrency):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        for code2, ms, e in res:
            if e:
                errs.append(e)
            else:
                lat.append(ms)
                statuses[code2] = statuses.get(code2, 0) + 1
        log('第 %d 轮完成（累计 %d 请求，错误 %d）' % (rnd, len(lat) + len(errs), len(errs)))
    wall = time.time() - wall0
    return summarize('mixed', base, concurrency, rounds, lat, errs, statuses, wall)


def scenario_login(base, concurrency):
    log('场景 login：%d 并发登录（验证 ip_username 锁定误伤）' % concurrency)
    lat, errs, statuses = [], [], {}
    wall0 = time.time()

    def one():
        c = HttpClient(base)
        t0 = time.time()
        try:
            code, body = login(c)
            return code, (time.time() - t0) * 1000, None, body
        except Exception as e:
            return None, (time.time() - t0) * 1000, '%s: %s' % (type(e).__name__, e), None

    threads, res = [], []
    lock = threading.Lock()
    def worker():
        r = one()
        with lock:
            res.append(r)
    for _ in range(concurrency):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    locked = 0
    for code, ms, e, body in res:
        if e:
            errs.append(e)
        else:
            lat.append(ms)
            statuses[code] = statuses.get(code, 0) + 1
            msg = (body or {}).get('message', '')
            if '锁定' in msg or 'lock' in str(msg).lower() or code == 423:
                locked += 1
    wall = time.time() - wall0
    summ = summarize('login', base, concurrency, 1, lat, errs, statuses, wall)
    summ['locked_requests'] = locked
    log('并发登录完成：成功 %d 锁定/受限 %d 错误 %d' % (statuses.get(200, 0), locked, len(errs)))
    return summ


def scenario_upload(base, concurrency):
    """并发上传 2MB 无效 zip：传输链路 + 并发排队观察；框架校验拒绝，不装插件。"""
    log('场景 upload：%d 并发 × 2MB 无效 zip' % concurrency)
    c = HttpClient(base, timeout=120)
    code, body = login(c)
    if code != 200:
        return {'error': 'login failed'}
    hdr = {'X-CSRF-Token': c.csrf}
    payload = b'not-a-zip' * (2 * 1024 * 1024 // 10)

    def one():
        c2 = HttpClient(base, timeout=120)
        c2.cookies = dict(c.cookies)
        t0 = time.time()
        try:
            # multipart 手拼（urllib 无内置）
            boundary = '----pcstress%s' % uuid.uuid4().hex
            head = ('--%s\r\nContent-Disposition: form-data; name="file"; filename="f%sb.zip"\r\n'
                    'Content-Type: application/zip\r\n\r\n' % (boundary, uuid.uuid4().int % 100000)).encode()
            tail = ('\r\n--%s--\r\n' % boundary).encode()
            body2 = head + payload + tail
            req = urllib.request.Request(c2.base + '/api/admin/plugins/upload', data=body2, method='POST',
                                         headers={'Content-Type': 'multipart/form-data; boundary=' + boundary,
                                                  'Cookie': '; '.join('%s=%s' % (k, v) for k, v in c2.cookies.items()),
                                                  'X-CSRF-Token': c2.csrf})
            resp = urllib.request.urlopen(req, timeout=120, context=_CTX)
            return resp.status, (time.time() - t0) * 1000, None
        except urllib.error.HTTPError as e:
            return e.code, (time.time() - t0) * 1000, None
        except Exception as e:
            return None, (time.time() - t0) * 1000, '%s: %s' % (type(e).__name__, e)

    threads, res, lat, errs, statuses, wall0 = [], [], [], [], {}, time.time()
    lock = threading.Lock()
    def worker():
        r = one()
        with lock:
            res.append(r)
    for _ in range(concurrency):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    for code2, ms, e in res:
        if e:
            errs.append(e)
        else:
            lat.append(ms)
            statuses[code2] = statuses.get(code2, 0) + 1
    wall = time.time() - wall0
    summ = summarize('upload', base, concurrency, 1, lat, errs, statuses, wall)
    log('并发上传完成：状态分布 %s 错误 %d' % (statuses, len(errs)))
    return summ


def summarize(scenario, base, concurrency, rounds, lat, errs, statuses, wall):
    lat.sort()
    n = len(lat)
    def pct(p):
        return lat[min(n - 1, int(n * p))] if n else None
    summ = {
        'scenario': scenario, 'base': base, 'concurrency': concurrency, 'rounds': rounds,
        'wall_s': round(wall, 1), 'total': n + len(errs), 'ok': n, 'errors': len(errs),
        'statuses': statuses,
        'p50_ms': round(pct(0.5), 1) if pct(0.5) is not None else None,
        'p90_ms': round(pct(0.9), 1) if pct(0.9) is not None else None,
        'p95_ms': round(pct(0.95), 1) if pct(0.95) is not None else None,
        'p99_ms': round(pct(0.99), 1) if pct(0.99) is not None else None,
        'max_ms': round(lat[-1], 1) if n else None,
        'throughput_rps': round(n / wall, 1) if wall > 0 else None,
        'sample_errors': errs[:10],
    }
    log('汇总：ok=%d errors=%d p50=%s p95=%s p99=%s rps=%s wall=%ss' %
        (summ['ok'], summ['errors'], summ['p50_ms'], summ['p95_ms'],
         summ['p99_ms'], summ['throughput_rps'], summ['wall_s']))
    return summ


def main():
    ap = argparse.ArgumentParser(description='FlaskToolkit PC 端压测（标准库）')
    ap.add_argument('--base', required=True, help='框架地址，如 https://127.0.0.1:5010')
    ap.add_argument('--scenario', choices=['mixed', 'login', 'upload'], default='mixed')
    ap.add_argument('--concurrency', type=int, default=100)
    ap.add_argument('--rounds', type=int, default=3)
    ap.add_argument('--out', default=None)
    ap.add_argument('--tag', default='')
    args = ap.parse_args()

    if args.scenario == 'mixed':
        summ = scenario_mixed(args.base, args.concurrency, args.rounds)
    elif args.scenario == 'login':
        summ = scenario_login(args.base, args.concurrency)
    else:
        summ = scenario_upload(args.base, args.concurrency)

    if args.out or True:
        os.makedirs(DIAG_DIR, exist_ok=True)
        ts = time.strftime('%Y%m%d_%H%M%S')
        out = args.out or os.path.join(DIAG_DIR, 'stress_%s_%s.json' % (args.scenario, ts))
        with open(out, 'w', encoding='utf-8') as f:
            json.dump({'tag': args.tag, 'time': ts, **summ}, f, ensure_ascii=False, indent=1)
        log('结果已写入：%s' % out)


if __name__ == '__main__':
    main()
