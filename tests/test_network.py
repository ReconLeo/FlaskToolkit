# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""局域网地址中心回归（v4.11 Reachability M1，core/network.py）

场景：
A. get_lan_addresses：mock socket.getaddrinfo / ipconfig / hostname -I / UDP 兜底
B. 过滤与去重：127.* / 169.254.* / IPv6 链路本地拒绝，重复 IP 去重
C. 绑定与端口：get_binding_host 优先级、register_effective_port / get_effective_port
D. 协议与 mDNS：get_scheme / is_https_enabled / get_mdns_hostname / is_mdns_enabled / get_mdns_url
E. get_access_urls：127.0.0.1 仅本机、0.0.0.0 全部可达 IP、mDNS 置顶、同 URL 去重
运行：python tests/test_network.py
"""
import os
import sys

sys.path.insert(0, _PROJECT_ROOT)

import global_var
from core import network

results = []

def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")


def main():
    import json
    import unittest.mock as mock

    # ---------- A. get_lan_addresses：getaddrinfo 来源 ----------
    with mock.patch.object(network.socket, 'gethostname', return_value='test-pc'):
        with mock.patch.object(network.socket, 'getaddrinfo', return_value=[
                (2, 1, 6, '', ('192.168.1.5', 0)),
                (10, 1, 6, '', ('fe80::1', 0, 0, 0)),
                (2, 1, 6, '', ('127.0.0.1', 0))]):
            addrs = network.get_lan_addresses()
    check('A1 getaddrinfo 取到局域网 IP', '192.168.1.5' in addrs, f'{addrs}')
    check('A2 过滤 127.*', '127.0.0.1' not in addrs, '')
    check('A3 过滤 IPv6 链路本地', all(':' not in a for a in addrs), '')

    # ---------- B. ipconfig（Windows）来源 + 去重 + 169.254 过滤 ----------
    ipcfg_text = ('\r\n以太网适配器 以太网:\r\n'
                  '   连接特定的 DNS 后缀 . . . . . . . :\r\n'
                  '   IPv4 地址 . . . . . . . . . . . . : 192.168.1.5\r\n'
                  '   IPv4 地址 . . . . . . . . . . . . : 10.0.0.8\r\n'
                  '   IPv4 地址 . . . . . . . . . . . . : 169.254.12.34\r\n'
                  '   默认网关. . . . . . . . . . . . . : 192.168.1.1\r\n')
    fake_run = mock.Mock(return_value=mock.Mock(stdout=ipcfg_text))
    with mock.patch.object(network, 'get_lan_addresses', return_value=[]):
        pass  # 占位防止误用
    with mock.patch.object(network.socket, 'gethostname', return_value='test-pc'):
        with mock.patch.object(network.socket, 'getaddrinfo', return_value=[]):
            with mock.patch.object(network.os, 'name', 'nt'):
                with mock.patch.object(network.subprocess, 'run', fake_run):
                    with mock.patch.object(network, 'get_lan_addresses', wraps=network.get_lan_addresses) as _w:
                        # 直接测内部流程：patch 平台命令后调用（wraps 原函数会再进命令分支）
                        addrs = network.get_lan_addresses()
    check('B1 ipconfig 取到多 IP', '192.168.1.5' in addrs and '10.0.0.8' in addrs, f'{addrs}')
    check('B2 过滤 169.254 链路本地', '169.254.12.34' not in addrs, '')
    check('B3 去重', addrs.count('192.168.1.5') == 1, '')

    # ---------- C. hostname -I（Linux/macOS）来源 ----------
    fake_run2 = mock.Mock(return_value=mock.Mock(stdout='192.168.1.9 172.16.0.2 127.0.0.1\n'))
    with mock.patch.object(network.socket, 'gethostname', return_value='test-pc'):
        with mock.patch.object(network.socket, 'getaddrinfo', return_value=[]):
            with mock.patch.object(network.os, 'name', 'posix'):
                with mock.patch.object(network.subprocess, 'run', fake_run2):
                    addrs = network.get_lan_addresses()
    check('C1 hostname -I 取到 IP', '192.168.1.9' in addrs and '172.16.0.2' in addrs, f'{addrs}')
    check('C2 过滤 127', '127.0.0.1' not in addrs, '')

    # ---------- D. UDP 兜底（全部来源为空） ----------
    fake_sock = mock.Mock()
    fake_sock.getsockname.return_value = ('10.1.2.3', 0)
    with mock.patch.object(network.socket, 'gethostname', return_value='test-pc'):
        with mock.patch.object(network.socket, 'getaddrinfo', return_value=[]):
            with mock.patch.object(network.os, 'name', 'posix'):
                with mock.patch.object(network.subprocess, 'run',
                                       mock.Mock(side_effect=Exception('no cmd'))):
                    with mock.patch.object(network.socket, 'socket', return_value=fake_sock):
                        addrs = network.get_lan_addresses()
    check('D1 UDP 兜底取出口 IP', '10.1.2.3' in addrs, f'{addrs}')

    # ---------- E. 绑定与端口 ----------
    saved_cfg = dict(global_var._user_config)
    try:
        global_var._user_config['HOST'] = '0.0.0.0'
        global_var._user_config['PORT'] = '5010'
        check('E1 get_binding_host 读配置', network.get_binding_host() == '0.0.0.0', '')
        network.register_effective_port(5077)
        check('E2 register_effective_port 优先', network.get_effective_port() == 5077, '')
        with mock.patch.dict(os.environ, {'FLASKTOOLKIT_HOST': '192.168.1.100'}, clear=False):
            check('E3 环境变量优先于配置', network.get_binding_host() == '192.168.1.100', '')
        # PORT 配置兜底（未注册）
        network.register_effective_port(None)
        with mock.patch.dict(os.environ, {'FLASKTOOLKIT_PORT': '5055'}, clear=False):
            check('E3b 环境变量 PORT 优先', network.get_effective_port() == 5055, '')
        global_var._user_config['PORT'] = '5022'
        check('E4 PORT 配置兜底', network.get_effective_port() == 5022, '')

        # ---------- F. 协议与 mDNS ----------
        with mock.patch.object(global_var, 'SSL_CERT_FILE', ''), \
             mock.patch.object(global_var, 'SSL_KEY_FILE', ''):
            check('F1 无证书 http', network.get_scheme() == 'http', '')
        with mock.patch.object(global_var, 'SSL_CERT_FILE', 'x.pem'), \
             mock.patch.object(global_var, 'SSL_KEY_FILE', 'y.pem'), \
             mock.patch.object(os.path, 'exists', return_value=True):
            check('F2 证书存在 https', network.get_scheme() == 'https', '')
            check('F3 is_https_enabled', network.is_https_enabled() is True, '')

        global_var._user_config['MDNS_ENABLED'] = True
        global_var._user_config['MDNS_HOSTNAME'] = 'mybox'
        check('F4 is_mdns_enabled', network.is_mdns_enabled() is True, '')
        check('F5 get_mdns_hostname', network.get_mdns_hostname() == 'mybox', '')
        check('F6 mdns_url 格式', network.get_mdns_url(5010) == 'http://mybox.local:5010', network.get_mdns_url(5010))
        global_var._user_config['MDNS_HOSTNAME'] = 'mybox.local'
        check('F7 .local 后缀防重复', network.get_mdns_hostname() == 'mybox', '')

        # ---------- G. get_access_urls ----------
        global_var._user_config['MDNS_ENABLED'] = False
        global_var._user_config['HOST'] = '127.0.0.1'
        network.register_effective_port(5010)
        with mock.patch.object(network, 'get_lan_addresses', return_value=['192.168.1.5']):
            items = network.get_access_urls()
        check('G1 127.0.0.1 仅本机', len(items) == 1 and items[0]['url'].endswith('127.0.0.1:5010'), f'{items}')

        global_var._user_config['HOST'] = '0.0.0.0'
        with mock.patch.object(network, 'get_lan_addresses', return_value=['192.168.1.5', '10.0.0.8', '192.168.1.5']):
            items = network.get_access_urls()
        check('G2 0.0.0.0 全部可达且去重',
              [i['url'] for i in items] == ['http://192.168.1.5:5010', 'http://10.0.0.8:5010'],
              f'{items}')

        global_var._user_config['MDNS_ENABLED'] = True
        with mock.patch.object(network, 'get_lan_addresses', return_value=['192.168.1.5']):
            items = network.get_access_urls()
        check('G3 mDNS 置顶', items[0]['kind'] == 'mdns' and items[0]['url'].endswith('.local:5010'), f'{items}')

        # ---------- H. EXTERNAL_SCHEME（反向代理 TLS 终止场景的静态协议声明） ----------
        saved_scheme = getattr(global_var, 'EXTERNAL_SCHEME', '')
        global_var.EXTERNAL_SCHEME = 'https'
        check('H1 EXTERNAL_SCHEME=https 时 get_scheme=https', network.get_scheme() == 'https', network.get_scheme())
        with mock.patch.object(network, 'get_lan_addresses', return_value=['192.168.1.5']):
            global_var._user_config['HOST'] = '0.0.0.0'
            items = network.get_access_urls()
        check('H2 外部 https 时访问地址为 https://',
              all(u['url'].startswith('https://') for u in items), f'{items}')
        check('H3 mDNS 地址随 scheme', network.get_mdns_url(5010).startswith('https://'),
              network.get_mdns_url(5010))
        global_var.EXTERNAL_SCHEME = 'http'
        check('H4 EXTERNAL_SCHEME=http 时 get_scheme=http', network.get_scheme() == 'http', '')
        global_var.EXTERNAL_SCHEME = 'ftp'
        check('H5 非法 EXTERNAL_SCHEME 回退自动判断',
              network.get_scheme() in ('http', 'https'), network.get_scheme())

        # ---------- I. EXTERNAL_HOST / EXTERNAL_PORT（反代分享地址外部入口） ----------
        saved_host = getattr(global_var, 'EXTERNAL_HOST', '')
        saved_xport = getattr(global_var, 'EXTERNAL_PORT', 0)
        global_var.EXTERNAL_SCHEME = 'https'
        global_var.EXTERNAL_HOST = 'ft.example.com'
        global_var.EXTERNAL_PORT = 8443
        with mock.patch.object(network, 'get_lan_addresses', return_value=['192.168.1.5']):
            global_var._user_config['HOST'] = '0.0.0.0'
            items = network.get_access_urls()
        check('I1 外部主机/端口置顶为分享入口',
              items[0]['kind'] == 'external'
              and items[0]['url'] == 'https://ft.example.com:8443',
              f'{items}')
        check('I2 get_external_port 优先外部端口',
              network.get_external_port() == 8443, str(network.get_external_port()))
        check('I3 get_external_host 返回配置',
              network.get_external_host() == 'ft.example.com', network.get_external_host())
        check('I4 mDNS 地址用外部端口',
              network.get_mdns_url().endswith('.local:8443'), network.get_mdns_url())
        global_var.EXTERNAL_HOST = ''
        global_var.EXTERNAL_PORT = 0
        global_var.EXTERNAL_SCHEME = saved_scheme
        check('I5 清空外部配置回退内部端口',
              network.get_external_port() == 5010 and network.get_external_host() == '',
              str(network.get_external_port()))
        global_var.EXTERNAL_HOST = saved_host
        global_var.EXTERNAL_PORT = saved_xport

        # ---------- J. HTTP→HTTPS 跳转服务器 + Secure Cookie 自动判定（v4.12 Secure） ----------
        import urllib.request
        from core.network import start_http_redirect, is_secure_cookie_mode

        class _NoRedirect(urllib.request.HTTPRedirectHandler):  # 禁用自动跟随，让 308 以 HTTPError 抛出
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        _opener = urllib.request.build_opener(_NoRedirect())
        redir_port, redir_err, redir_srv = start_http_redirect('127.0.0.1', 5099)
        check('J1 跳转服务器启动', redir_port is not None and redir_err is None, f'{redir_port}')
        if redir_srv:
            try:
                req = urllib.request.Request(f'http://127.0.0.1:{redir_port}/foo?x=1')
                try:
                    _opener.open(req, timeout=5)
                    check('J2 GET 308 跳转', False, '未跳转')
                except urllib.error.HTTPError as e:
                    loc = e.headers.get('Location', '')
                    check('J2 GET 308 跳转 https 主端口',
                          e.code == 308 and loc == 'https://127.0.0.1:5099/foo?x=1', f'{e.code} {loc}')
                try:
                    req2 = urllib.request.Request(f'http://127.0.0.1:{redir_port}/api', data=b'x' * 10, method='POST')
                    _opener.open(req2, timeout=5)
                    check('J3 POST 308 保留方法', False, '未跳转')
                except urllib.error.HTTPError as e:
                    check('J3 POST 308 保留方法',
                          e.code == 308 and e.headers.get('Location', '').endswith('/api'),
                          f'{e.code}')
            finally:
                redir_srv.shutdown()
                redir_srv.server_close()

        saved_scs = getattr(global_var, 'SESSION_COOKIE_SECURE', None)
        try:
            global_var.SESSION_COOKIE_SECURE = None
            global_var.EXTERNAL_SCHEME = 'https'
            check('J4 自动模式 + 外部 https → Secure 开启', is_secure_cookie_mode() is True, '')
            global_var.EXTERNAL_SCHEME = ''
            global_var.SSL_CERT_FILE = ''
            global_var.SSL_KEY_FILE = ''
            check('J5 自动模式 + 纯 HTTP → Secure 关闭', is_secure_cookie_mode() is False, '')
            global_var.SESSION_COOKIE_SECURE = True
            check('J6 显式 True 强制开启', is_secure_cookie_mode() is True, '')
            global_var.SESSION_COOKIE_SECURE = False
            global_var.EXTERNAL_SCHEME = 'https'
            check('J7 显式 False 强制关闭（HTTP 兼容场景）', is_secure_cookie_mode() is False, '')
        finally:
            global_var.SESSION_COOKIE_SECURE = saved_scs
            global_var.EXTERNAL_SCHEME = saved_scheme
    finally:
        global_var._user_config.clear()
        global_var._user_config.update(saved_cfg)
        network.register_effective_port(None)

    print(f'\n==== 局域网地址中心（v4.11 M1）：共 {len(results)} 项，'
          f'通过 {sum(1 for _, c, _ in results if c)}，'
          f'失败 {sum(1 for _, c, _ in results if not c)} ====')
    ok = all(c for _, c, _ in results)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
