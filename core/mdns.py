# -*- coding: utf-8 -*-
"""core/mdns.py — v4.11 Reachability M2：mDNS 主机名服务注册（可选依赖 zeroconf）

解决"非固定 IP 每次都要重新发布访问链接"的痛点：注册后访问者用
``http://<hostname>.local:port`` 访问，IP 变了链接不变。

- 配置 ``MDNS_ENABLED``（默认关，安全导向，后台"网络与访问"页一键开启）与
  ``MDNS_HOSTNAME``（默认 flasktoolkit）
- 依赖 ``zeroconf``（纯 Python 无 C 依赖，可选）：缺失时 ``start`` 返回 False
  并打印安装提示，框架照常运行（与 v4.10 M1 的"可选依赖增强"理念一致）
- 注册 ``_flasktoolkit._tcp.local.`` 服务，端口取运行时实际端口
  （network.register_effective_port），properties 携带版本与系统名
- 生命周期：``start(port)`` 在 app 启动后调用；``stop()`` 接入关闭钩子；
  均幂等（重复 start 先 stop / 直接返回）
"""
import logging
import socket

import global_var
from core import network

logger = logging.getLogger('flask.app')

# mDNS 服务类型（RFC 6763：_<name>._tcp.local.）
SERVICE_TYPE = '_flasktoolkit._tcp.local.'

_zc = None        # zeroconf.Zeroconf 实例（运行时状态）
_info = None      # 已注册的 ServiceInfo


def available() -> bool:
    """zeroconf 是否已安装（未安装返回 False，功能禁用）。"""
    try:
        import zeroconf  # noqa: F401
        return True
    except ImportError:
        return False


def is_active() -> bool:
    """当前是否已注册 mDNS 服务（运行时状态，区别于配置 MDNS_ENABLED）。"""
    return _zc is not None


def get_service_name() -> str:
    """服务实例名：<hostname>._flasktoolkit._tcp.local.。"""
    return f"{network.get_mdns_hostname()}.{SERVICE_TYPE}"


def start(port=None, hostname=None) -> bool:
    """注册 mDNS 服务（幂等）。返回 True=已注册；False=未启用/缺库/失败。"""
    global _zc, _info
    if _zc is not None:
        return True  # 已注册，幂等
    if not network.is_mdns_enabled():
        return False  # 配置未开启
    try:
        import zeroconf
    except ImportError:
        logger.warning("mDNS 功能需要可选依赖 zeroconf，请安装：pip install zeroconf"
                       "（未安装不影响框架运行）", extra={'plugin': 'system'})
        return False
    try:
        port = port or network.get_effective_port()
        hostname = hostname or network.get_mdns_hostname()
        service_name = f"{hostname}.{SERVICE_TYPE}"
        _zc = zeroconf.Zeroconf()

        # 广播本机可达 IP 的 A 记录（无网卡时留空交由 zeroconf 自行处理）
        lan_ips = network.get_lan_addresses()
        addresses = [socket.inet_aton(ip) for ip in lan_ips] if lan_ips else None

        # 兼容 zeroconf 版本差异：新版 ServiceInfo 用 addresses 列表，旧版用 address
        props = {
            'version': global_var.FRAMEWORK_VERSION,
            'system_name': str(global_var.get_user_config().get('SYSTEM_NAME') or 'FlaskToolkit'),
        }
        try:
            _info = zeroconf.ServiceInfo(SERVICE_TYPE, service_name,
                                         addresses=addresses, port=port, properties=props)
        except TypeError:
            _info = zeroconf.ServiceInfo(SERVICE_TYPE, service_name,
                                         address=addresses[0] if addresses else None,
                                         port=port, properties=props)
        _zc.register_service(_info)
        logger.info(f"mDNS 服务已注册: {service_name}（{network.get_mdns_url(port)}）",
                    extra={'plugin': 'system'})
        return True
    except Exception as e:
        logger.warning(f"mDNS 服务注册失败: {e}", extra={'plugin': 'system'})
        stop()
        return False


def stop() -> None:
    """注销 mDNS 服务（幂等）。"""
    global _zc, _info
    if _zc is None:
        return
    try:
        if _info is not None:
            _zc.unregister_service(_info)
    except Exception:
        pass
    try:
        _zc.close()
    except Exception:
        pass
    _zc = None
    _info = None
    logger.info("mDNS 服务已注销", extra={'plugin': 'system'})
