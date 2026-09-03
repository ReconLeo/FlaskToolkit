# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""开发运维工具（tools/）回归：backup / reset / config
隔离 /tmp 目录（mock global_var.BASE_DIR / USER_CONFIG_FILE），不污染真实项目。

覆盖：
- backup：create 备份 6 类关键内容（配置/状态/数据/日志/清单）、不备份临时目录；list / info；篡改后 restore 还原
- reset：factory_reset plugins 范围保护内置（status.json/audit.log 不动）、builtin 范围不报错
- config：show 输出标题与配置项；set 写入隔离配置并生效；非法值拒绝（exit 1）；unset 移除恢复默认
运行：python tests/test_tools_ops.py
"""
import argparse
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile

import global_var
from core.factory_reset import factory_reset

results = []


def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")


def main():
    isolated = tempfile.mkdtemp(prefix='ftk_tools_')
    saved_base = global_var.BASE_DIR
    saved_ucfg = global_var.USER_CONFIG_FILE
    saved_pim = getattr(global_var, 'PACKAGE_INTEGRITY_MODE', None)
    try:
        global_var.BASE_DIR = isolated

        # ---------- 构造隔离项目数据 ----------
        os.makedirs(os.path.join(isolated, 'plugins', 'configs'))
        os.makedirs(os.path.join(isolated, 'plugins', 'data'))
        os.makedirs(os.path.join(isolated, 'plugins', 'data', 'auth'))
        os.makedirs(os.path.join(isolated, 'data'))
        os.makedirs(os.path.join(isolated, 'logs'))
        os.makedirs(os.path.join(isolated, 'temp'))
        open(os.path.join(isolated, 'plugins', 'configs', 'auth.json'), 'w', encoding='utf-8').write(
            json.dumps({"users": [{"username": "admin"}]}))
        open(os.path.join(isolated, 'plugins', 'status.json'), 'w', encoding='utf-8').write('{"demo": {}}')
        open(os.path.join(isolated, 'plugins', 'data', 'auth', 'sessions.json'), 'w', encoding='utf-8').write('{}')
        open(os.path.join(isolated, 'data', 'stats.json'), 'w', encoding='utf-8').write('{}')
        open(os.path.join(isolated, 'data', 'audit.log'), 'w', encoding='utf-8').write('audit')
        open(os.path.join(isolated, 'data', 'frontend_tools.json'), 'w', encoding='utf-8').write('[]')
        open(os.path.join(isolated, 'logs', 'app.log'), 'w', encoding='utf-8').write('log')
        open(os.path.join(isolated, 'temp', 'x.zip'), 'w', encoding='utf-8').write('z')

        # ============ 1. backup：create / list / info / restore ============
        from tools import backup as bk

        dest, saved, skipped = bk.create_backup('b1')
        check('backup create 生成备份目录', os.path.isdir(dest), dest)
        check('backup create 备份 6 类内容',
              set(saved) == {'plugins/configs', 'plugins/status.json', 'plugins/data', 'data',
                             'data/frontend_tools.json', 'logs'}, f"{saved}")
        check('backup create 内容落盘',
              os.path.exists(os.path.join(dest, 'plugins', 'configs', 'auth.json')) and
              os.path.exists(os.path.join(dest, 'data', 'audit.log')) and
              os.path.exists(os.path.join(dest, 'backup.json')), "")
        check('backup create 不备份 temp（临时文件）', not os.path.exists(os.path.join(dest, 'temp')), "")

        backs = bk.list_backups()
        check('backup list 列出备份', any(b['name'] == 'b1' for b in backs), f"{backs}")
        info = bk.info_backup('b1')
        check('backup info 含 6 条目', len(info['items']) == 6, f"{info['items']}")

        # 篡改项目数据后 restore
        open(os.path.join(isolated, 'data', 'audit.log'), 'w', encoding='utf-8').write('TAMPERED')
        open(os.path.join(isolated, 'plugins', 'configs', 'auth.json'), 'w', encoding='utf-8').write('{}')
        restored = bk.restore_backup('b1')
        check('backup restore 恢复条目', 'data' in restored and 'plugins/configs' in restored, f"{restored}")
        check('backup restore 数据还原',
              open(os.path.join(isolated, 'data', 'audit.log'), encoding='utf-8').read() == 'audit', "")
        check('backup restore 配置还原',
              json.load(open(os.path.join(isolated, 'plugins', 'configs', 'auth.json'), encoding='utf-8'))
              ['users'][0]['username'] == 'admin', "")

        # ============ 2. reset：factory_reset 范围 ============
        res = factory_reset(['plugins'])
        check('reset plugins 保留内置 status.json',
              os.path.exists(os.path.join(isolated, 'plugins', 'status.json')), "")
        check('reset plugins 不动 audit.log',
              os.path.exists(os.path.join(isolated, 'data', 'audit.log')), "")
        check('reset plugins 清理 0 项（无自定义插件）', res.get('cleaned') == [], f"{res.get('cleaned')}")
        res = factory_reset(['builtin'])
        check('reset builtin 不报错', 'cleaned' in res, f"{res}")

        # ============ 3. config：show / set / 非法值 / unset ============
        import tools.config as cfg
        cfg.USER_CONFIG_FILE = os.path.join(isolated, 'data', 'user_config.json')
        global_var.USER_CONFIG_FILE = cfg.USER_CONFIG_FILE

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cfg.cmd_show(None)
        out = buf.getvalue()
        check('config show 输出标题', '配置项' in out, "")
        check('config show 含关键配置项',
              'PACKAGE_INTEGRITY_MODE' in out and 'PACKAGE_MAX_UPLOAD_SIZE_MB' in out and 'LOG_DIR' in out, "")

        ns = argparse.Namespace(key='PACKAGE_INTEGRITY_MODE', value='strict')
        with contextlib.redirect_stdout(io.StringIO()):
            cfg.cmd_set(ns)
        check('config set 写入隔离文件',
              json.load(open(cfg.USER_CONFIG_FILE, encoding='utf-8')).get('PACKAGE_INTEGRITY_MODE') == 'strict', "")
        check('config set 后生效值更新', getattr(global_var, 'PACKAGE_INTEGRITY_MODE', None) == 'strict',
              f"{getattr(global_var, 'PACKAGE_INTEGRITY_MODE', None)}")

        ns = argparse.Namespace(key='PACKAGE_INTEGRITY_MODE', value='bogus')
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                cfg.cmd_set(ns)
            check('config set 非法值被拒（exit 1）', False, '未退出')
        except SystemExit:
            check('config set 非法值被拒（exit 1）', True, '')

        ns = argparse.Namespace(key='PACKAGE_INTEGRITY_MODE')
        with contextlib.redirect_stdout(io.StringIO()):
            cfg.cmd_unset(ns)
        check('config unset 移除配置',
              'PACKAGE_INTEGRITY_MODE' not in json.load(open(cfg.USER_CONFIG_FILE, encoding='utf-8')), "")

        print(f'\n==== 开发运维工具回归：共 {len(results)} 项，通过 {sum(1 for _, c, _ in results if c)}，'
              f'失败 {sum(1 for _, c, _ in results if not c)} ====')
    finally:
        global_var.BASE_DIR = saved_base
        global_var.USER_CONFIG_FILE = saved_ucfg
        if saved_pim is not None:
            global_var.PACKAGE_INTEGRITY_MODE = saved_pim
        try:
            shutil.rmtree(isolated, ignore_errors=True)
        except Exception:
            pass

    ok = all(c for _, c, _ in results)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
