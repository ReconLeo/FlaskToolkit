# -*- coding: utf-8 -*-
"""tools/desktop_launcher.py（v4.11 M5 桌面启动器）回归。

隔离 USER_CONFIG_FILE 到 /tmp，不污染真实 data/user_config.json。
覆盖：
- prepare_config：共享/本机写 HOST、保留其它配置键
- extract_port_from_output：http/https/中文输出/无端口
- generate_access_info：端口注册、地址列表、mDNS 状态字段、共享模式地址
- monitor_output：行回调/端口回调/退出回调（模拟子进程输出）
- start_server：FLASKTOOLKIT_PORT 环境变量注入（mock Popen）
- main --smoke 全链路（进程内运行，输出含绑定地址/端口/访问地址/mDNS）

运行：python tests/test_desktop_launcher.py
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile

# 项目根路径自动推导，不依赖绝对路径
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_TESTS_DIR)
sys.path.insert(0, _PROJECT_ROOT)

sys.path.insert(0, os.path.join(_PROJECT_ROOT, 'tools'))

import global_var
import desktop_launcher

results = []


def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")


def main():
    isolated = tempfile.mkdtemp(prefix='ftk_launcher_')
    saved_ucfg = global_var.USER_CONFIG_FILE
    saved_launcher_ucfg = desktop_launcher.USER_CONFIG_FILE
    iso_cfg = os.path.join(isolated, 'user_config.json')
    # 预置隔离配置（含原 HOST 与其它键）
    with open(iso_cfg, 'w', encoding='utf-8') as f:
        json.dump({'HOST': '127.0.0.1', 'PACKAGE_INTEGRITY_MODE': 'warn'}, f)
    try:
        global_var.USER_CONFIG_FILE = iso_cfg
        desktop_launcher.USER_CONFIG_FILE = iso_cfg

        # ---------- prepare_config ----------
        h = desktop_launcher.prepare_config(shared=True)
        data = json.load(open(iso_cfg, encoding='utf-8'))
        check('prepare_config(shared=True) 返回 0.0.0.0', h == '0.0.0.0', repr(h))
        check('prepare_config 共享模式写 HOST=0.0.0.0', data.get('HOST') == '0.0.0.0', str(data))
        check('prepare_config 保留其它配置键', data.get('PACKAGE_INTEGRITY_MODE') == 'warn', '')

        h2 = desktop_launcher.prepare_config(shared=False)
        data2 = json.load(open(iso_cfg, encoding='utf-8'))
        check('prepare_config(shared=False) 写 HOST=127.0.0.1',
              h2 == '127.0.0.1' and data2.get('HOST') == '127.0.0.1', repr(h2))

        # ---------- extract_port_from_output ----------
        check('extract http 端口', desktop_launcher.extract_port_from_output('Running on http://127.0.0.1:5011') == 5011, '')
        check('extract https 端口', desktop_launcher.extract_port_from_output('Serving on https://0.0.0.0:8443') == 8443, '')
        check('extract 中文输出端口', desktop_launcher.extract_port_from_output('服务启动地址: http://192.168.1.5:5010') == 5010, '')
        check('extract 无端口返回 None', desktop_launcher.extract_port_from_output('FlaskToolkit 启动完成') is None, '')

        # ---------- generate_access_info ----------
        info = desktop_launcher.generate_access_info(port='5011', shared=False)
        check('generate_access_info 端口生效', info['port'] == 5011, str(info['port']))
        check('generate_access_info 绑定主机', info['host'] == '127.0.0.1', info['host'])
        check('generate_access_info urls 非空', len(info['urls']) >= 1, str([u['url'] for u in info['urls']]))
        check('generate_access_info url 含端口', all(':5011' in u['url'] for u in info['urls']), '')
        check('generate_access_info mdns 字段', 'mdns_enabled' in info and 'mdns_hostname' in info, '')
        check('generate_access_info lan_addresses 为列表', isinstance(info['lan_addresses'], list), '')

        info_shared = desktop_launcher.generate_access_info(port='5011', shared=True)
        check('generate_access_info 共享模式 urls 为局域网',
              len(info_shared['urls']) >= 1 and all(u['kind'] == 'lan' for u in info_shared['urls']),
              str([u['url'] for u in info_shared['urls']]))

        # ---------- monitor_output（模拟子进程输出流） ----------
        events = []

        class FakeStdout:
            def __init__(self, lines):
                self._lines = iter(lines)

            def __iter__(self):
                return self

            def __next__(self):
                return next(self._lines)

        class FakeProc:
            def __init__(self, lines):
                self.stdout = FakeStdout(lines)

        proc = FakeProc(['[1] 初始化...', 'Running on http://0.0.0.0:5011', '[2] 已就绪'])
        t = desktop_launcher.monitor_output(
            proc,
            lambda line: events.append(('line', line)),
            lambda p: events.append(('port', p)),
            lambda p: events.append(('exit', p)))
        t.join(timeout=5)
        check('monitor_output 回传全部行', sum(1 for e in events if e[0] == 'line') == 3, str(events))
        check('monitor_output 端口回调', ('port', 5011) in events, str(events))
        check('monitor_output 退出回调携带端口', ('exit', 5011) in events, str(events))

        # ---------- start_server env 注入（mock Popen，不真启动框架） ----------
        captured = {}
        real_popen = desktop_launcher.subprocess.Popen

        def fake_popen(cmd, **kw):
            captured['cmd'] = cmd
            captured['env'] = kw.get('env')
            captured['creationflags'] = kw.get('creationflags', 0)

            class _P:
                def __init__(self):
                    self.stdout = None

                def poll(self):
                    return 0

            return _P()

        desktop_launcher.subprocess.Popen = fake_popen
        try:
            desktop_launcher.start_server(port='5011')
            check('start_server 注入 FLASKTOOLKIT_PORT',
                  captured['env'].get('FLASKTOOLKIT_PORT') == '5011',
                  str(captured['env'].get('FLASKTOOLKIT_PORT')))
            check('start_server 启动 app.py',
                  bool(captured['cmd']) and str(captured['cmd'][-1]).endswith('app.py'),
                  str(captured.get('cmd')))
            check('start_server 无弹窗标志', captured['creationflags'] != 0, str(captured['creationflags']))
            desktop_launcher.start_server(port='abc')
            check('start_server 非法端口不注入 env', 'FLASKTOOLKIT_PORT' not in captured['env'], '')
        finally:
            desktop_launcher.subprocess.Popen = real_popen

        # ---------- main --smoke 全链路（进程内，配置已隔离） ----------
        out = io.StringIO()
        old_argv = sys.argv
        sys.argv = ['desktop_launcher.py', '--smoke', '--shared', '--port', '5012']
        try:
            with contextlib.redirect_stdout(out):
                rc = desktop_launcher.main()
        finally:
            sys.argv = old_argv
        out_txt = out.getvalue()
        check('main --smoke 返回 0', rc == 0, str(rc))
        check('main --smoke 输出绑定地址', '绑定地址: 0.0.0.0' in out_txt, '')
        check('main --smoke 输出端口 5012', '端口: 5012' in out_txt, '')
        check('main --smoke 输出访问地址', '访问地址' in out_txt and 'http://' in out_txt, '')
        check('main --smoke 输出 mDNS 状态', 'mDNS' in out_txt, '')

        print(f'\n==== 桌面启动器回归：共 {len(results)} 项，通过 {sum(1 for _, c, _ in results if c)}，'
              f'失败 {sum(1 for _, c, _ in results if not c)} ====')
    finally:
        global_var.USER_CONFIG_FILE = saved_ucfg
        desktop_launcher.USER_CONFIG_FILE = saved_launcher_ucfg
        try:
            shutil.rmtree(isolated, ignore_errors=True)
        except Exception:
            pass

    ok = all(c for _, c, _ in results)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
