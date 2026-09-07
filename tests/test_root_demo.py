# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""v4.15.1 示例插件 root_demo 回归（框架 Root 域 framework:core 演示）

覆盖：
A. plugin.json 声明一致性（capabilities/permission/require_framework_version）
B. Root 授权：framework:core 注册后 check_framework('root_demo','core') 放行，隐含 read
C. Root 写：check_filesystem 写框架核心配置 data/user_config.json → declared:framework:core
D. 核心读：filesystem:read:data/ 声明下读 data/user_config.json → 放行
E. 对照：仅 filesystem:write 的插件写 app.py → framework-core-not-declared
F. 自属路径隐式豁免不受影响
G. root_demo.py 模块可加载，类元信息正确

运行：python tests/test_root_demo.py
"""
import importlib.util
import json
import os
import sys

sys.path.insert(0, _PROJECT_ROOT)

from core import capabilities as C

results = []


def check(name, cond, detail=''):
    results.append((name, bool(cond), detail))


# ------------------------------ A. plugin.json ------------------------------
_plug_dir = os.path.join(_PROJECT_ROOT, 'examples', 'plugins', 'root_demo')
with open(os.path.join(_plug_dir, 'plugin.json'), encoding='utf-8') as _f:
    _desc = json.load(_f)
_caps = _desc.get('capabilities', [])
check("A1 plugin.json name=root_demo", _desc.get('name') == 'root_demo', '')
check("A2 permission=admin", _desc.get('permission') == 'admin', '')
check("A3 require_framework_version=4.15.0", _desc.get('require_framework_version') == '4.15.0', '')
check("A4 声明 framework:core", 'framework:core' in _caps, '%s' % _caps)
check("A5 声明 filesystem:read:data/", 'filesystem:read:data/' in _caps, '%s' % _caps)

# ------------------------------ B. Root 授权 ------------------------------
C.register_capabilities('root_demo', _caps)
ok, reason = C.check_framework('root_demo', 'core')
check("B1 check_framework('root_demo','core') 放行", ok, reason)
ok_r, _ = C.check_framework('root_demo', 'read')
check("B2 framework:core 隐含 read", ok_r, '')

# ------------------------------ C. Root 写核心 ------------------------------
okw, rw = C.check_filesystem('root_demo', 'data/user_config.json', 'w')
check("C1 Root 写核心配置放行（declared:framework:core）", okw and rw == 'declared:framework:core', rw)
# 写任意框架核心路径（app.py）也放行（Root 覆盖全部核心）
okw2, rw2 = C.check_filesystem('root_demo', 'app.py', 'w')
check("C2 Root 写 app.py 放行", okw2, rw2)

# ------------------------------ D. 核心读 ------------------------------
okr, rr = C.check_filesystem('root_demo', 'data/user_config.json', 'r')
check("D1 读核心配置放行（filesystem:read:data/）", okr, rr)

# ------------------------------ E. 对照拒绝 ------------------------------
C.register_capabilities('demo_no_root', ['filesystem:write:data/'])
ok5, r5 = C.check_filesystem('demo_no_root', 'app.py', 'w')
check("E1 仅 filesystem:write 写核心被拒", (not ok5) and r5 == 'framework-core-not-declared', r5)
# 普通插件写自属 data 目录仍放行（不受核心收紧影响）
ok6, r6 = C.check_filesystem('demo_no_root', 'data/demo.json', 'w')
check("E2 普通插件写 data 目录放行", ok6, r6)
C.unregister_capabilities('demo_no_root')

# ------------------------------ F. 自属路径豁免 ------------------------------
ok7, r7 = C.check_filesystem('root_demo', 'plugins/data/root_demo/x.json', 'w')
check("F1 自属路径隐式豁免", ok7, r7)
C.unregister_capabilities('root_demo')

# ------------------------------ G. root_demo.py 模块 ------------------------------
_py = os.path.join(_plug_dir, 'root_demo.py')
_spec = importlib.util.spec_from_file_location('root_demo', _py)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
_cls = _mod.RootDemoPlugin
check("G1 类名 RootDemoPlugin", _cls.__name__ == 'RootDemoPlugin', '')
check("G2 类 name=root_demo", _cls.name == 'root_demo', '')
check("G3 类 require_framework_version=4.15.0", _cls.require_framework_version == '4.15.0', '')
check("G4 类 permission=admin", _cls.permission == 'admin', '')
_check_target = getattr(_mod, '_TARGET_CONFIG', None)
check("G5 写目标为 data/user_config.json（框架核心路径）", _check_target == 'data/user_config.json', '%s' % _check_target)
check("G6 写目标命中框架核心（is_framework_core_path）",
      __import__('core.framework_manifest', fromlist=['is_framework_core_path']).is_framework_core_path(_check_target) is True, '')

# ============ 汇总 ============
n_pass = sum(1 for _, c, _ in results if c)
n_fail = len(results) - n_pass
for name, c, detail in results:
    if not c:
        print("[FAIL] %s %s" % (name, detail))
print("\n==== 示例插件 root_demo 回归（v4.15.1）：共 %d 项，通过 %d，失败 %d ====" % (len(results), n_pass, n_fail))
sys.exit(1 if n_fail else 0)
