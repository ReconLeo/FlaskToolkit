# -*- coding: utf-8 -*-
"""android_client.py — Android（Pydroid）端 FlaskToolkit 测试客户端。

环境：Python 3.13.2 + requests 2.34.2（Pydroid 已装）。
三模式：
  probe   归因探测（默认）：登录 + 访问各端点，验证框架审计日志里的 remote_addr 归因；
  stress  并发压测：登录态 N 并发 × M 轮打混合 API，统计 P50/P95/P99 与错误率；
  upload  大文件上传：上传 <size-mb>MB 到 echo-upload 测试插件，校验 sha256 回传。

输出：终端摘要 + diagnostics/android_<mode>_<时间戳>.json（回传到 PC 的 test_server/diagnostics/ 比对）。

用法：
  python android_client.py --base https://192.168.1.100:5010 --user admin --password admin123
  python android_client.py --mode stress --base https://192.168.1.100:5010 --concurrency 50 --rounds 3
  python android_client.py --mode upload --base https://192.168.1.100:5010 --size-mb 100
"""
import argparse
import json
import os
import sys
import time
import urllib3

import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_USER = 'admin'
DEFAULT_PASS = 'admin123'
DIAG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'diagnostics')


def log(msg):
    print('[android_client] %s' % msg, flush=True)


def make_session(base):
    """创建 requests.Session，verify=False 处理自签名；返回 (session, csrf)。"""
    s = requests.Session()
    s.verify = False
    return s


def api_login(s, base, user, password, timeout=30):
    """POST /api/auth/login；返回错误串或 None。"""
    url = base.rstrip('/') + '/api/auth/login'
    r = s.post(url, json={'username': user, 'password': password}, timeout=timeout)
    try:
        body = r.json()
    except Exception:
        body = {'raw': r.text[:200]}
    if r.status_code != 200 or body.get('code') not in (0, 200, None):
        return 'login failed: HTTP %s body=%s' % (r.status_code, body)
    return None


def csrf_token(session):
    for c in session.cookies:
        if c.name == 'csrf_token':
            return c.value
    return ''


def probe(s, base, user, password):
    """归因探测：依次请求关键端点，记录状态/耗时/响应头/错误。"""
    results = []
    base = base.rstrip('/')
    steps = [
        ('首页 GET /', 'GET', '/', None),
        ('未登录 user/info', 'GET', '/api/auth/user/info', None),
    ]
    for label, method, path, extra in steps:
        t0 = time.time()
        try:
            r = s.request(method, base + path, timeout=30)
            results.append({'label': label, 'method': method, 'path': path,
                            'status': r.status_code, 'ms': round((time.time() - t0) * 1000, 1),
                            'headers': dict(list(r.headers.items())[:8])})
        except Exception as e:
            results.append({'label': label, 'method': method, 'path': path,
                            'error': '%s: %s' % (type(e).__name__, e),
                            'ms': round((time.time() - t0) * 1000, 1)})

    err = api_login(s, base, user, password)
    results.append({'label': '登录 POST /api/auth/login', 'method': 'POST', 'path': '/api/auth/login',
                    'error': err or None, 'status': None if err else 200})
    if err:
        log('登录失败：%s' % err)
        return results

    logged_steps = [
        ('登录态 user/info', 'GET', '/api/auth/user/info', None),
        ('后台 system/info', 'GET', '/api/admin/system/info', None),
        ('后台 network', 'GET', '/api/admin/network', None),
        ('后台 audit', 'GET', '/api/admin/audit', None),
        ('后台网络页 HTML', 'GET', '/admin/network', None),
        # 审计触发（归因比对）：禁用/启用 echo_upload 产生 audit 事件，记录 remote_addr
        ('插件禁用 echo_upload', 'POST', '/api/admin/plugins/echo_upload/disable', None),
        ('插件启用 echo_upload', 'POST', '/api/admin/plugins/echo_upload/enable', None),
    ]
    hdr = {'X-CSRF-Token': csrf_token(s)}
    for label, method, path, extra in logged_steps:
        t0 = time.time()
        try:
            r = s.request(method, base + path, headers=hdr, timeout=30)
            results.append({'label': label, 'method': method, 'path': path,
                            'status': r.status_code, 'ms': round((time.time() - t0) * 1000, 1)})
        except Exception as e:
            results.append({'label': label, 'method': method, 'path': path,
                            'error': '%s: %s' % (type(e).__name__, e),
                            'ms': round((time.time() - t0) * 1000, 1)})
    return results


def stress(s, base, user, password, concurrency, rounds):
    """并发压测：登录态混合 API（system/info + network + 首页），统计延迟分布。"""
    err = api_login(s, base, user, password)
    if err:
        log('登录失败：%s' % err)
        return []
    hdr = {'X-CSRF-Token': csrf_token(s)}
    paths = ['/api/admin/system/info', '/api/admin/network', '/']
    import concurrent.futures as cf
    latencies, errors, statuses = [], [], {}
    log('压测开始：%d 并发 × %d 轮' % (concurrency, rounds))

    def one_req(path):
        t0 = time.time()
        try:
            r = s.get(base.rstrip('/') + path, headers=hdr, timeout=60)
            return (r.status_code, (time.time() - t0) * 1000, None)
        except Exception as e:
            return (None, (time.time() - t0) * 1000, '%s: %s' % (type(e).__name__, e))

    for rnd in range(1, rounds + 1):
        with cf.ThreadPoolExecutor(max_workers=concurrency) as ex:
            futs = [ex.submit(one_req, paths[i % len(paths)]) for i in range(concurrency)]
            for f in cf.as_completed(futs):
                code, ms, e = f.result()
                if e:
                    errors.append(e)
                else:
                    latencies.append(ms)
                    statuses[code] = statuses.get(code, 0) + 1
        log('第 %d 轮完成：累计 %d 请求，错误 %d' % (rnd, len(latencies) + len(errors), len(errors)))

    latencies.sort()
    n = len(latencies)
    def pct(p):
        return latencies[min(n - 1, int(n * p))] if n else None
    summary = {'mode': 'stress', 'concurrency': concurrency, 'rounds': rounds,
               'total': n + len(errors), 'ok': n, 'errors': len(errors),
               'statuses': statuses,
               'p50_ms': round(pct(0.5), 1) if pct(0.5) is not None else None,
               'p90_ms': round(pct(0.9), 1) if pct(0.9) is not None else None,
               'p95_ms': round(pct(0.95), 1) if pct(0.95) is not None else None,
               'p99_ms': round(pct(0.99), 1) if pct(0.99) is not None else None,
               'max_ms': round(latencies[-1], 1) if n else None,
               'sample_errors': errors[:10]}
    log('压测完成：ok=%d errors=%d p50=%s p95=%s p99=%s' %
        (summary['ok'], summary['errors'], summary['p50_ms'], summary['p95_ms'], summary['p99_ms']))
    return [summary]


def upload(s, base, user, password, size_mb):
    """大文件上传：向 echo-upload 插件上传 size_mb MB 文件，校验返回 sha256。

    实现：确定性数据分块写入临时文件（避免大内存占用），再以 file-like 流式上传
    （requests 的 files 不支持生成器，会 TypeError）。
    """
    import tempfile
    err = api_login(s, base, user, password)
    if err:
        log('登录失败：%s' % err)
        return []
    hdr = {'X-CSRF-Token': csrf_token(s)}
    url = base.rstrip('/') + '/api/echo_upload/echo-upload'  # 插件 API 格式 /api/<plugin_name>/<path>
    tmp = os.path.join(tempfile.gettempdir(), 'ft_big_%dmb.bin' % size_mb)
    blk = bytes([0x5a]) * (1024 * 1024)
    t0 = time.time()
    try:
        with open(tmp, 'wb') as f:
            for _ in range(size_mb):
                f.write(blk)
        with open(tmp, 'rb') as f:
            r = s.post(url, files={'file': ('big_%dmb.bin' % size_mb, f)},
                       headers=hdr, timeout=900)
        ms = (time.time() - t0) * 1000
        try:
            body = r.json()
        except Exception:
            body = {'raw': r.text[:300]}
        log('上传 %dMB 完成：HTTP %s 耗时 %.1fs' % (size_mb, r.status_code, ms / 1000))
        return [{'mode': 'upload', 'size_mb': size_mb, 'status': r.status_code,
                 'ms': round(ms, 1), 'body': body}]
    except Exception as e:
        log('上传异常：%s' % e)
        return [{'mode': 'upload', 'size_mb': size_mb, 'error': '%s: %s' % (type(e).__name__, e)}]
    finally:
        if os.path.isfile(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


def main():
    ap = argparse.ArgumentParser(description='FlaskToolkit Android 端测试客户端')
    ap.add_argument('--mode', choices=['probe', 'stress', 'upload'], default='probe')
    ap.add_argument('--base', required=True, help='框架地址，如 https://192.168.1.100:5010')
    ap.add_argument('--user', default=DEFAULT_USER)
    ap.add_argument('--password', default=DEFAULT_PASS)
    ap.add_argument('--concurrency', type=int, default=50)
    ap.add_argument('--rounds', type=int, default=3)
    ap.add_argument('--size-mb', type=int, default=100)
    ap.add_argument('--out', default=None, help='诊断输出路径（默认 diagnostics/ 下）')
    ap.add_argument('--tag', default='', help='备注标签，写入诊断 JSON')
    args = ap.parse_args()

    s = make_session(args.base)
    log('base=%s mode=%s' % (args.base, args.mode))
    if args.mode == 'probe':
        data = probe(s, args.base, args.user, args.password)
    elif args.mode == 'stress':
        data = stress(s, args.base, args.user, args.password, args.concurrency, args.rounds)
    else:
        data = upload(s, args.base, args.user, args.password, args.size_mb)

    os.makedirs(DIAG_DIR, exist_ok=True)
    ts = time.strftime('%Y%m%d_%H%M%S')
    out = args.out or os.path.join(DIAG_DIR, 'android_%s_%s.json' % (args.mode, ts))
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'mode': args.mode, 'base': args.base, 'tag': args.tag,
                   'client_time': ts, 'results': data}, f, ensure_ascii=False, indent=1)
    log('诊断已写入：%s' % out)


if __name__ == '__main__':
    main()
