# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""mDNS 主机名服务回归（v4.11 Reachability M2，core/mdns.py）

场景：
A. 缺库降级：zeroconf 未安装（mock import 抛 ImportError）→ start False + 不崩溃
B. 配置开关：MDNS_ENABLED=False 时即使 zeroconf 可用也不注册（默认安全）
C. 注册/注销：mock zeroconf 模块注入 sys.modules，验证 register/unregister/close
D. 幂等：重复 start 不重复注册；stop 后再 start 可重新注册
E. 失败回滚：register_service 抛异常 → start False + 清理实例
F. 服务名与 available/is_active/get_service_name
运行：python tests/test_mdns.py
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
    import builtins
    import types
    import unittest.mock as mock

    from core import mdns

    saved_cfg = dict(global_var._user_config)

    # ---------- 构造假 zeroconf 模块 ----------
    fake_zc_mod = types.ModuleType('zeroconf')

    class FakeZeroconf:
        instances = []
        def __init__(self, *a, **kw):
            self.registered = []
            self.closed = False
            FakeZeroconf.instances.append(self)
        def register_service(self, info):
            self.registered.append(info)
        def unregister_service(self, info):
            if info in self.registered:
                self.registered.remove(info)
        def close(self):
            self.closed = True

    class FakeServiceInfo:
        def __init__(self, *a, **kw):
            self.args = (a, kw)

    fake_zc_mod.Zeroconf = FakeZeroconf
    fake_zc_mod.ServiceInfo = FakeServiceInfo

    def _inject():
        sys.modules['zeroconf'] = fake_zc_mod

    def _eject():
        sys.modules.pop('zeroconf', None)

    try:
        global_var._user_config['MDNS_ENABLED'] = True
        global_var._user_config['MDNS_HOSTNAME'] = 'testbox'
        network.register_effective_port(5099)
        with mock.patch.object(network, 'get_lan_addresses', return_value=['192.168.1.5']):
            # ---------- F. 服务名与状态 ----------
            check('F1 get_service_name', mdns.get_service_name() == 'testbox._flasktoolkit._tcp.local.',
                  mdns.get_service_name())
            check('F2 is_active 初始 False', mdns.is_active() is False, '')

            # ---------- B. 未开启时不注册 ----------
            global_var._user_config['MDNS_ENABLED'] = False
            _inject()
            try:
                ok = mdns.start()
            finally:
                _eject()
            check('B1 MDNS_ENABLED=False start 返回 False', ok is False, '')
            check('B2 未创建实例', len(FakeZeroconf.instances) == 0, '')

            # ---------- A. 缺库降级 ----------
            global_var._user_config['MDNS_ENABLED'] = True
            real_import = builtins.__import__
            def fake_import(name, *a, **kw):
                if name == 'zeroconf':
                    raise ImportError('No module named zeroconf')
                return real_import(name, *a, **kw)
            with mock.patch.object(builtins, '__import__', fake_import):
                ok = mdns.start()
            check('A1 缺库 start 返回 False', ok is False, '')
            check('A2 缺库不崩溃且未注册', mdns.is_active() is False, '')

            # ---------- C. 正常注册 ----------
            _inject()
            try:
                ok = mdns.start()
            finally:
                _eject()
            check('C1 start 返回 True', ok is True, '')
            check('C2 is_active True', mdns.is_active() is True, '')
            check('C3 创建 1 个实例', len(FakeZeroconf.instances) == 1, '')
            info = FakeZeroconf.instances[-1].registered
            check('C4 已注册 1 个服务', len(info) == 1, '')
            if info:
                # FakeServiceInfo.args = ((位置参数...), {kwargs...})
                positional = info[0].args[0]
                kwargs = info[0].args[1]
                check('C5 服务名正确',
                      len(positional) >= 2 and positional[1] == 'testbox._flasktoolkit._tcp.local.',
                      str(positional))
                check('C6 端口与地址正确',
                      kwargs.get('port') == 5099 and kwargs.get('addresses') is not None,
                      str(kwargs))
                check('C7 properties 携带版本',
                      kwargs.get('properties', {}).get('version') == global_var.FRAMEWORK_VERSION,
                      str(kwargs.get('properties')))

            # ---------- D. 幂等 ----------
            _inject()
            try:
                ok2 = mdns.start()
            finally:
                _eject()
            check('D1 重复 start 幂等返回 True', ok2 is True, '')
            check('D2 未重复创建实例', len(FakeZeroconf.instances) == 1, '')
            check('D3 未重复注册', len(FakeZeroconf.instances[0].registered) == 1, '')

            # ---------- stop ----------
            mdns.stop()
            check('D4 stop 后 is_active False', mdns.is_active() is False, '')
            check('D5 unregister 清空', len(FakeZeroconf.instances[0].registered) == 0, '')
            check('D6 close 已调用', FakeZeroconf.instances[0].closed is True, '')

            # ---------- E. 失败回滚 ----------
            _inject()
            try:
                with mock.patch.object(FakeZeroconf, 'register_service',
                                       side_effect=RuntimeError('bind fail')):
                    ok = mdns.start()
            finally:
                _eject()
            check('E1 注册异常 start 返回 False', ok is False, '')
            check('E2 失败后实例被清理', mdns.is_active() is False, '')

            # ---------- D7. stop 后可重新注册 ----------
            _inject()
            try:
                ok = mdns.start()
            finally:
                _eject()
            check('D7 停止后可重新注册', ok is True and mdns.is_active() is True, '')
            mdns.stop()
    finally:
        _eject()
        global_var._user_config.clear()
        global_var._user_config.update(saved_cfg)
        network.register_effective_port(None)
        mdns.stop()

    print(f'\n==== mDNS 主机名服务（v4.11 M2）：共 {len(results)} 项，'
          f'通过 {sum(1 for _, c, _ in results if c)}，'
          f'失败 {sum(1 for _, c, _ in results if not c)} ====')
    ok = all(c for _, c, _ in results)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
