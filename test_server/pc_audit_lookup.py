# -*- coding: utf-8 -*-
"""pc_audit_lookup.py — 多机 IP 归因比对：从 data/audit.log 提取指定窗口的审计事件。

用法（Android 端 probe 回传诊断 JSON 后）：
  # 提取某时间点之后的所有审计事件（看 Android 请求期间框架记录的 remote_addr）
  python test_server/pc_audit_lookup.py --since "2026-09-06 22:50:00"

  # 只看某个 IP（如 Android 局域网 IP）的登录/审计事件
  python test_server/pc_audit_lookup.py --since "22:50:00" --ip 192.168.1.50

  # 只看某个动作
  python test_server/pc_audit_lookup.py --since "22:50:00" --action 登录

判定：Android probe 诊断 JSON 里记录的是"客户端看到的响应"；本工具输出的是"框架记录的来源 IP"。
两者时间窗口对齐后，audit 的 ip 字段应等于 Android 局域网 IP（直连与反代场景都应成立）。
"""
import argparse
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT_LOG = os.path.join(BASE_DIR, 'data', 'audit.log')


def norm(t):
    """时间串归一化比较：'22:50:00' 或 '2026-09-06 22:50:00'。"""
    return t.strip()


def time_part(t):
    """取时间部分：'2026-09-06 21:41:36' → '21:41:36'。"""
    return t.split(' ')[-1]


def main():
    ap = argparse.ArgumentParser(description='审计日志 IP 归因比对')
    ap.add_argument('--since', default='', help='起始时间（含，如 22:50:00 或 2026-09-06 22:50:00）')
    ap.add_argument('--until', default='', help='结束时间（含，默认不限）')
    ap.add_argument('--ip', default='', help='过滤来源 IP（如 192.168.1.50）')
    ap.add_argument('--action', default='', help='过滤动作（如 登录/插件安装）')
    ap.add_argument('--last', type=int, default=200, help='最多输出条数（默认 200）')
    ap.add_argument('--only-ip', action='store_true', help='只输出 ip 字段汇总')
    args = ap.parse_args()

    if not os.path.isfile(AUDIT_LOG):
        print('audit.log 不存在：%s' % AUDIT_LOG, file=sys.stderr)
        sys.exit(1)

    hits = []
    with open(AUDIT_LOG, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            t = str(e.get('time', ''))
            _since, _until = norm(args.since), norm(args.until)
            if _since:
                _tk = norm(t) if ' ' in _since else time_part(norm(t))
                if _tk < _since:
                    continue
            if _until:
                _tk = norm(t) if ' ' in _until else time_part(norm(t))
                if _tk > _until:
                    continue
            if args.ip and str(e.get('ip', '')) != args.ip:
                continue
            if args.action and args.action not in str(e.get('action', '')):
                continue
            hits.append(e)

    hits.sort(key=lambda x: str(x.get('time', '')))
    hits = hits[-args.last:] if args.last > 0 else hits
    print('命中 %d 条（%s 起%s）' % (
        len(hits), args.since or '不限',
        '，IP=%s' % args.ip if args.ip else ''))
    if args.only_ip:
        ips = {}
        for e in hits:
            ip = str(e.get('ip', '-'))
            ips[ip] = ips.get(ip, 0) + 1
        for ip, n in sorted(ips.items(), key=lambda x: -x[1]):
            print('  %-18s %d 条' % (ip, n))
        return
    for e in hits:
        print('%s | ip=%-16s | %s | %s | %s' % (
            e.get('time', ''), e.get('ip', '-'), e.get('actor', ''),
            e.get('action', ''), str(e.get('detail', ''))[:80]))


if __name__ == '__main__':
    main()
