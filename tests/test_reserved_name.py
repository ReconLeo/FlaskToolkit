# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""插件名保留名黑名单校验专项单元测试：core/plugin_pack.py 的 parse_plugin_pack

背景（v4.21 目录化）：插件 name 直接映射到 plugins/<name>/、templates/plugins/<name>/、
templates/plugins/static/<name>/，与框架保留目录/模块/内置插件同 namespace。安装保留名
插件会：覆盖框架保留目录（plugins/data|configs|temp）、因 scan _skip_top 而静默不可加载、
且 Factory Reset 无法清理残留。故 parse_plugin_pack 对 PLUGIN_RESERVED_NAMES 全部拒绝。

覆盖场景：
1. 数据驱动：逐一构造 name=各保留名 的最小合法包，断言 parse_plugin_pack 抛 ValueError
   （消息含"保留名"）。
2. 正常插件名（demo_meta）仍能解析（回归）。

运行：python test_reserved_name.py（不依赖 Flask 服务，纯单元测试）
"""
import json
import os
import shutil
import sys
import tempfile
import zipfile

sys.path.insert(0, _PROJECT_ROOT)

import global_var
from core.plugin_pack import parse_plugin_pack
from core.framework_manifest import PLUGIN_RESERVED_NAMES

results = []

def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

class TmpBase:
    """临时项目根：mock global_var.BASE_DIR，测试后清理（try/except 容忍）"""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix='reserved_')
        self._old = None

    def __enter__(self):
        self._old = global_var.BASE_DIR
        global_var.BASE_DIR = self.root
        return self.root

    def __exit__(self, *exc):
        global_var.BASE_DIR = self._old
        try:
            shutil.rmtree(self.root, ignore_errors=True)
        except Exception:
            pass  # 清理失败不阻断测试（如受限环境）

GOOD_PY = '''
from plugins.base_plugin import BasePlugin

class DemoMetaPlugin(BasePlugin):
    name = "demo_meta"
    version = "1.0.0"
    title = "普通插件"
    author = "Test"
    category = "测试"
    description = "普通插件"
    permission = "user"
'''

def _make_pack(zip_path, plugin_name):
    """构造最小合法插件包：plugin.json name=plugin_name + 主 .py"""
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('plugin.json',
                    json.dumps({'name': plugin_name, 'version': '1.0.0'}, ensure_ascii=False).encode('utf-8'))
        zf.writestr(f'{plugin_name}.py', b'class P: pass')


def test_reserved_names_rejected():
    """数据驱动：黑名单内每个保留名均被 parse_plugin_pack 拒绝"""
    with TmpBase() as root:
        for name in PLUGIN_RESERVED_NAMES:
            zp = os.path.join(root, f'{name}.zip')
            _make_pack(zp, name)
            try:
                parse_plugin_pack(zp)
                check(f'保留名 {name} 拒绝', False, '未抛异常！')
            except ValueError as e:
                check(f'保留名 {name} 拒绝', '保留名' in str(e), str(e)[:60])


def test_normal_name_ok():
    """回归：普通插件名仍能正常解析"""
    with TmpBase() as root:
        zp = os.path.join(root, 'ok.zip')
        _make_pack(zp, 'demo_meta')
        desc = parse_plugin_pack(zp)
        check('普通名 demo_meta 解析通过', desc.get('name') == 'demo_meta', f"desc={desc}")


def test_blacklist_not_empty():
    """黑名单非空且含关键保留目录（防止未来误删）"""
    check('黑名单含 data', 'data' in PLUGIN_RESERVED_NAMES, f"len={len(PLUGIN_RESERVED_NAMES)}")
    check('黑名单含 configs', 'configs' in PLUGIN_RESERVED_NAMES, '')
    check('黑名单含 temp', 'temp' in PLUGIN_RESERVED_NAMES, '')
    check('黑名单含 __init__', '__init__' in PLUGIN_RESERVED_NAMES, '')
    check('黑名单含 base_plugin', 'base_plugin' in PLUGIN_RESERVED_NAMES, '')
    check('黑名单含 status', 'status' in PLUGIN_RESERVED_NAMES, '')
    check('黑名单含 static', 'static' in PLUGIN_RESERVED_NAMES, '')
    check('黑名单含 auth', 'auth' in PLUGIN_RESERVED_NAMES, '')
    check('黑名单含 user_manage', 'user_manage' in PLUGIN_RESERVED_NAMES, '')


if __name__ == '__main__':
    test_reserved_names_rejected()
    test_normal_name_ok()
    test_blacklist_not_empty()

    passed = sum(1 for _, c, _ in results if c)
    print(f"\n==== 保留名黑名单 共 {len(results)} 项，通过 {passed}，失败 {len(results) - passed} ====")
    sys.exit(0 if passed == len(results) else 1)
