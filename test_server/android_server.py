# -*- coding: utf-8 -*-
"""android_server.py — Android（Pydroid）端 Flask 微型服务器（可选，反向链路诊断）。

用途：在 Android 上模拟"另一台被访问设备"，PC 端脚本反向访问它，
用于验证反向链路的 IP 归因与可达性（与多机归因复测互补）。

端点：
  GET  /             回显访问者 IP、请求头、时间
  GET  /health       健康检查
  POST /upload       multipart 接收文件，返回大小 + sha256

用法（Pydroid 内）：
  python android_server.py --port 8080
  # 然后在 PC 上：curl -k https://<Android_IP>:8080/  或 本目录 pc_stress.py 反向访问
"""
import argparse
import hashlib
import json
import time

from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route('/')
def index():
    return jsonify({
        'service': 'android-test-server',
        'time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'client_ip': request.remote_addr,
        'x_forwarded_for': request.headers.get('X-Forwarded-For', ''),
        'host': request.host,
        'headers': dict(list(request.headers.items())[:12]),
    })


@app.route('/health')
def health():
    return jsonify({'ok': True, 'time': time.time()})


@app.route('/upload', methods=['POST'])
def upload():
    f = request.files.get('file')
    if f is None:
        return jsonify({'error': '缺少 file 字段'}), 400
    h = hashlib.sha256()
    size = 0
    while True:
        blk = f.stream.read(1024 * 1024)
        if not blk:
            break
        h.update(blk)
        size += len(blk)
    return jsonify({'size': size, 'sha256': h.hexdigest(),
                    'client_ip': request.remote_addr})


def main():
    ap = argparse.ArgumentParser(description='Android 端 Flask 微型服务器（反向链路诊断）')
    ap.add_argument('--host', default='0.0.0.0')
    ap.add_argument('--port', type=int, default=8080)
    args = ap.parse_args()
    print('android-server 监听 %s:%s' % (args.host, args.port), flush=True)
    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == '__main__':
    main()
