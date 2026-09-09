# -*- coding: utf-8 -*-
"""core/network.py — v4.11 Reachability：局域网地址发现与可达地址生成

解决"非固定 IP 每次都要重新发布访问链接"的痛点：
- 跨平台获取本机非 loopback IPv4（纯标准库，无第三方依赖）
- 组合"可达访问地址"（IP:port / .local 主机名:port），供后台网络页 / 启动横幅 /
  桌面启动器（tools/desktop_launcher.py）使用
- mDNS 主机名（.local）地址组合：v4.11 M2 配套（zeroconf 为可选依赖，缺失时
  仅无法注册服务，地址组合逻辑不依赖 zeroconf）

安全默认：不绑定 0.0.0.0 时仅返回本机地址；mDNS 默认关闭（MDNS_ENABLED=False），
由管理员在后台"网络与访问"页一键开启。
"""
import logging
import os
import re
import socket
import subprocess

import global_var

logger = logging.getLogger('flask.app')

# 默认 mDNS 主机名（可经 MDNS_HOSTNAME 配置覆盖，如 flasktoolkit.local）
DEFAULT_MDNS_HOSTNAME = 'flasktoolkit'

# 链路本地 / 保留地址前缀（IPv4 部分；IPv6 链路本地 fe80:: 单独过滤）
_FILTER_PREFIXES = ('127.', '169.254.', '0.0.0.0')

# 运行时实际端口（app.py 启动后由 register_effective_port 记录；未注册时回退配置/默认）
_effective_port = None


def get_hostname() -> str:
    """机器主机名（mDNS 主机名基座；失败返回 'localhost'）。"""
    try:
        return socket.gethostname()
    except Exception:
        return 'localhost'


def _is_usable_ipv4(ip) -> bool:
    """过滤：仅保留可用的 IPv4 局域网地址（拒绝 loopback/链路本地/全零）。"""
    if not isinstance(ip, str) or '.' not in ip or ':' in ip:
        return False
    for prefix in _FILTER_PREFIXES:
        if ip.startswith(prefix):
            return False
    # 粗校验四段数字
    parts = ip.split('.')
    if len(parts) != 4:
        return False
    for p in parts:
        if not p.isdigit() or int(p) > 255:
            return False
    return True


def get_lan_addresses() -> list:
    """获取所有非 loopback 的 IPv4 局域网地址（纯标准库，跨平台）。

    顺序：socket.getaddrinfo(hostname) → 平台命令（Windows ipconfig /
    Linux-macOS hostname -I）→ UDP connect 兜底（取出口 IP，不发包）。
    去重保留顺序；全部失败返回 []（调用方自行降级）。
    """
    addresses = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if _is_usable_ipv4(ip):
                addresses.append(ip)
    except Exception:
        pass

    try:
        if os.name == 'nt':
            import locale
            encoding = locale.getpreferredencoding() or 'gbk'
            try:
                out = subprocess.run(['ipconfig'], capture_output=True, text=True,
                                     encoding=encoding, errors='replace', timeout=5).stdout or ''
                for line in out.splitlines():
                    m = re.search(r'IPv4[^:]*:\s*(\d+\.\d+\.\d+\.\d+)', line)
                    if m and _is_usable_ipv4(m.group(1)):
                        addresses.append(m.group(1))
            except Exception:
                pass
        else:
            try:
                out = subprocess.run(['hostname', '-I'], capture_output=True,
                                     text=True, timeout=5).stdout or ''
                for ip in out.split():
                    ip = ip.strip()
                    if _is_usable_ipv4(ip):
                        addresses.append(ip)
            except Exception:
                pass
    except Exception:
        pass

    addresses = list(dict.fromkeys(addresses))
    if addresses:
        return addresses

    # UDP 兜底：connect 仅做路由查找不发包，取本机出口 IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('10.254.254.254', 1))
            ip = s.getsockname()[0]
            if _is_usable_ipv4(ip):
                addresses.append(ip)
        finally:
            s.close()
    except Exception:
        pass
    return list(dict.fromkeys(addresses))


def get_binding_host() -> str:
    """当前绑定地址（环境变量 FLASKTOOLKIT_HOST > user_config.HOST > 127.0.0.1）。"""
    env = os.environ.get('FLASKTOOLKIT_HOST', '').strip()
    if env:
        return env
    try:
        return str(global_var.get_user_config().get('HOST') or '127.0.0.1')
    except Exception:
        return '127.0.0.1'


def register_effective_port(port) -> None:
    """记录运行时实际端口（app.py 启动后调用；自动探测端口场景必需）。"""
    global _effective_port
    _effective_port = int(port) if port else None


def get_effective_port() -> int:
    """实际端口：运行时注册值 > FLASKTOOLKIT_PORT 环境变量 > PORT 配置 > 5000。"""
    if _effective_port:
        return _effective_port
    env = os.environ.get('FLASKTOOLKIT_PORT', '').strip()
    if env.isdigit():
        return int(env)
    try:
        cfg = str(global_var.get_user_config().get('PORT') or '').strip()
        if cfg.isdigit():
            return int(cfg)
    except Exception:
        pass
    return 5000


def is_https_enabled() -> bool:
    """HTTPS 是否启用（SSL_CERT_FILE/SSL_KEY_FILE 均配置且文件存在）。"""
    try:
        cert = global_var.SSL_CERT_FILE
        key = global_var.SSL_KEY_FILE
        return bool(cert and key and os.path.exists(cert) and os.path.exists(key))
    except Exception:
        return False


def get_scheme() -> str:
    """当前访问协议（https/http）。

    优先级：EXTERNAL_SCHEME 显式声明（反向代理 TLS 终止场景，如 'https'）
    > 直连自签名 HTTPS（SSL_CERT_FILE/SSL_KEY_FILE 均配置且存在）> http。
    非法 EXTERNAL_SCHEME 值自动回退按证书判断。
    """
    external = str(getattr(global_var, 'EXTERNAL_SCHEME', '') or '').strip().lower()
    if external in ('https', 'http'):
        return external
    return 'https' if is_https_enabled() else 'http'


def get_mdns_hostname() -> str:
    """mDNS 主机名（配置 MDNS_HOSTNAME 或默认 flasktoolkit；去除 .local 后缀防重复）。"""
    try:
        name = str(global_var.get_user_config().get('MDNS_HOSTNAME') or '').strip() \
            or DEFAULT_MDNS_HOSTNAME
    except Exception:
        name = DEFAULT_MDNS_HOSTNAME
    name = name.replace('.local', '')
    return name or DEFAULT_MDNS_HOSTNAME


def is_mdns_enabled() -> bool:
    """mDNS 注册开关（默认关，安全导向；页面/配置开启）。"""
    try:
        return bool(global_var.get_user_config().get('MDNS_ENABLED'))
    except Exception:
        return False


def get_ip_watch_interval() -> int:
    """IP 变化检测间隔（秒，配置 IP_WATCH_INTERVAL，0=关闭；默认 30）。

    注意不能用 ``v or 30`` 兜底（0 会被吞成 30）。"""
    try:
        v = global_var.get_user_config().get('IP_WATCH_INTERVAL')
        return int(v) if v not in (None, '') else 30
    except Exception:
        return 30


def get_external_port() -> int:
    """外部访问端口：EXTERNAL_PORT>0（反向代理场景，Nginx 监听端口）时用之，否则内部端口。"""
    try:
        p = int(getattr(global_var, 'EXTERNAL_PORT', 0) or 0)
    except (TypeError, ValueError):
        p = 0
    return p if p > 0 else get_effective_port()


def get_external_host() -> str:
    """外部访问主机/域名（EXTERNAL_HOST 配置；反向代理场景分享地址输出外部入口）。"""
    return str(getattr(global_var, 'EXTERNAL_HOST', '') or '').strip()


def get_mdns_url(port=None) -> str:
    """mDNS 主机名访问地址（scheme://<hostname>.local:port）。"""
    port = port or get_external_port()
    return f"{get_scheme()}://{get_mdns_hostname()}.local:{port}"


def get_access_urls(port=None) -> list:
    """组合可达访问地址列表（供网络页/横幅/启动器展示与分享）。

    返回 [{'label': str, 'url': str, 'kind': 'local'|'lan'|'mdns'}, ...]：
    - mdns：mDNS 开启时置顶（链接不随 IP 变化，优先分享）
    - 绑定 127.0.0.1 仅本机时：只返回本机地址（kind=local，提示需开启共享）
    - 绑定 0.0.0.0 / 具体 IP：返回全部可达 IP（kind=lan，去重）
    - EXTERNAL_HOST 配置（反向代理场景）：置顶返回外部入口（kind=external，host/端口取外部配置）
    """
    port = port or get_external_port()
    scheme = get_scheme()
    external_host = get_external_host()
    items = []

    if external_host:
        # 反向代理：分享地址输出外部入口（内部地址对外不可达）
        items.append({'label': '外部地址',
                      'url': f'{scheme}://{external_host}:{port}',
                      'kind': 'external'})
        if is_mdns_enabled():
            items.append({'label': 'mDNS 主机名', 'url': get_mdns_url(port), 'kind': 'mdns'})
        seen, result = set(), []
        for it in items:
            if it['url'] not in seen:
                seen.add(it['url'])
                result.append(it)
        return result

    if is_mdns_enabled():
        items.append({'label': 'mDNS 主机名', 'url': get_mdns_url(port), 'kind': 'mdns'})

    binding = get_binding_host()
    lan_ips = get_lan_addresses()
    if binding and binding not in ('0.0.0.0', '::'):
        # 绑定具体地址：127.0.0.1 时仅本机；绑定某 IP 时该 IP 若可达也列出
        if binding == '127.0.0.1' or binding.startswith('127.'):
            items.append({'label': '本机', 'url': f'{scheme}://127.0.0.1:{port}', 'kind': 'local'})
        elif binding in lan_ips:
            items.append({'label': '本机', 'url': f'{scheme}://{binding}:{port}', 'kind': 'lan'})
        else:
            items.append({'label': '绑定地址', 'url': f'{scheme}://{binding}:{port}', 'kind': 'lan'})
    else:
        # 0.0.0.0：全部可达 IP
        for ip in lan_ips:
            items.append({'label': '局域网', 'url': f'{scheme}://{ip}:{port}', 'kind': 'lan'})

    # 去重（同 url 保留首个）
    seen, result = set(), []
    for it in items:
        if it['url'] not in seen:
            seen.add(it['url'])
            result.append(it)
    return result


# ------------------------------ v4.12 Secure：HTTP→HTTPS 跳转 + Secure Cookie 自动判定 ------------------------------

def start_http_redirect(host, https_port):
    """HTTPS 直连模式下启动 HTTP→HTTPS 自动跳转端口（https_port+1，被占用自动探测）。

    浏览器/curl 访问 ``http://host:<跳转端口>`` 时以 **308**（保留 POST 方法与 body）
    跳转到 ``https://host:<https_port><原路径>``。Host 头取主机部分（兼容 IPv6 [::1]）。

    返回 (redirect_port, None, server) 成功 / (None, 错误消息, None) 失败；
    跳转服务器为 daemon 线程，随进程退出自动回收（测试可 server.shutdown 手动关闭）。
    仅直连 HTTPS 模式启用（反向代理场景跳转由 Nginx 负责）。
    """
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from core.utils import get_available_port, is_port_available

    class _RedirectHandler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def handle_one_request(self):
            """v4.15.4：苹果 https:// 访问本 HTTP 跳转端口时容错。

            TLS ClientHello 无换行，http.server 默认在 readline 阶段阻塞。这里先
            peek 首字节，识别 TLS 握手（ContentType: handshake/ccs/alert/appdata，
            或 SSLv2 0x80）后返回友好提示，避免连接挂起；其余正常走父类解析。
            """
            try:
                first = self.rfile.peek(1)[:1]
            except Exception:
                first = b''
            if first in (b'\x16', b'\x17', b'\x14', b'\x15', b'\x80'):
                self._refuse_tls()
                return
            super().handle_one_request()

        def parse_request(self):
            """v4.15.4：请求行可读但版本解析失败（如 Bad HTTP/0.9）时容错。

            父类 super().parse_request() 失败会调 send_error 发送默认错误；send_error
            已被 override 为友好提示，因此这里只需确保连接结束即可。
            """
            try:
                return super().parse_request()
            except Exception:
                self.close_connection = True
                return False

        def send_error(self, code, message=None, explain=None):
            """v4.15.4：所有错误响应统一给友好提示，不再暴露 Bad HTTP/0.9 等内部错误。"""
            body = (f'HTTP 跳转端口：请使用 http:// 访问本端口以自动跳转到 HTTPS，'
                    f'或直接访问 https://{https_port} 主端口。').encode('utf-8')
            try:
                self.request_version = self.request_version or 'HTTP/1.0'
                self.requestline = getattr(self, 'requestline', '')
                self.send_response(code)  # 不传父类 message，避免泄露 Bad HTTP/0.9 等内部错误
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                self.wfile.flush()
            except Exception:
                pass
            self.close_connection = True

        def _refuse_tls(self):
            """向 TLS 探测返回友好提示：说明这是 HTTP 跳转端口，应使用 http:// 或直连 https:// 主端口。"""
            body = (f'HTTP 跳转端口：请使用 http:// 访问本端口以自动跳转到 HTTPS，'
                    f'或直接访问 https://{https_port} 主端口。').encode('utf-8')
            try:
                self.request_version = getattr(self, 'request_version', None) or 'HTTP/1.1'
                self.requestline = ''
                self.send_response(400, 'Bad Request')
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                self.wfile.flush()
            except Exception:
                pass
            self.close_connection = True

        def log_error(self, fmt, *args):
            """抑制协议解析错误刷屏（send_error 已自定义响应）。"""
            pass

        def _jump(self):
            # 消费请求体：单线程 HTTPServer 若不读 body，POST/PUT 等带体请求会在
            # 客户端发送 body 阶段被 RST（WinError 10053），且残留体污染下一请求行
            cl = self.headers.get('Content-Length')
            if cl:
                try:
                    remain = int(cl)
                except (TypeError, ValueError):
                    remain = 0
                while remain > 0:
                    chunk = self.rfile.read(min(remain, 65536))
                    if not chunk:
                        break
                    remain -= len(chunk)
            raw_host = (self.headers.get('Host', '') or host).strip()
            host_part = raw_host.rsplit(':', 1)[0] if ':' in raw_host else raw_host
            host_part = host_part.strip('[]')
            target = f'https://{host_part}:{https_port}{self.path}'
            self.send_response(308)
            self.send_header('Location', target)
            self.send_header('Content-Length', '0')
            self.end_headers()

        do_GET = do_POST = do_HEAD = do_PUT = do_DELETE = do_OPTIONS = _jump

        def log_message(self, fmt, *args):  # 抑制访问日志刷屏
            pass

    redirect_port = https_port + 1
    if not is_port_available(redirect_port):
        redirect_port = get_available_port(start_port=https_port + 1)
    try:
        server = HTTPServer((host, redirect_port), _RedirectHandler)
    except OSError as e:
        return None, f'HTTP 跳转端口启动失败（{e}）', None
    threading.Thread(target=server.serve_forever, daemon=True,
                     name='http-redirect').start()
    return redirect_port, None, server


def is_secure_cookie_mode() -> bool:
    """会话/CSRF Cookie Secure 属性判定。

    优先级：SESSION_COOKIE_SECURE 显式配置（True=强制 / False=强制关闭）>
    自动——HTTPS 直连（SSL_CERT_FILE/SSL_KEY_FILE 生效）或反向代理外部 https
    （EXTERNAL_SCHEME=https）时自动开启 Secure，纯 HTTP 局域网自动关闭
    （否则浏览器会丢弃非 https 下的 Secure Cookie）。
    """
    v = getattr(global_var, 'SESSION_COOKIE_SECURE', None)
    if v is True:
        return True
    if v is False:
        return False
    # 自动：跟随**当前请求实际协议**（ProxyFix 后 request.scheme 已反映外部协议，
    # 反代 https 场景为 https、内部 HTTP 直连为 http）。v4.12.1 修复（F10）：
    # 不再受 EXTERNAL_SCHEME 全局联动——内部 http 直连时关闭 Secure，
    # 否则 Secure cookie 被 http 客户端（浏览器/requests）丢弃导致登录态失效。
    try:
        from flask import request
        if request.scheme == 'https':
            return True
        return False
    except RuntimeError:
        # 无请求上下文（启动横幅/CLI）：回退全局协议推导
        return get_scheme() == 'https'
