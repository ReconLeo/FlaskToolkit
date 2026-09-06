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
    """当前访问协议（https/http）。"""
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


def get_mdns_url(port=None) -> str:
    """mDNS 主机名访问地址（http://<hostname>.local:port）。"""
    port = port or get_effective_port()
    return f"{get_scheme()}://{get_mdns_hostname()}.local:{port}"


def get_access_urls(port=None) -> list:
    """组合可达访问地址列表（供网络页/横幅/启动器展示与分享）。

    返回 [{'label': str, 'url': str, 'kind': 'local'|'lan'|'mdns'}, ...]：
    - mdns：mDNS 开启时置顶（链接不随 IP 变化，优先分享）
    - 绑定 127.0.0.1 仅本机时：只返回本机地址（kind=local，提示需开启共享）
    - 绑定 0.0.0.0 / 具体 IP：返回全部可达 IP（kind=lan，去重）
    """
    port = port or get_effective_port()
    scheme = get_scheme()
    items = []

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
