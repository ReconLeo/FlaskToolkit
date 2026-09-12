# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""v4.15.1 框架目录清单统一回归（core/framework_manifest.py 单一事实来源）

覆盖：
A. 清单一致性：selfcheck/update/backup 均复用 manifest（同一对象，无硬编码漂移）
B. CORE_FILES / CORE_DIRS 完整性：清单内文件/目录在项目根真实存在
C. is_framework_core_path 边界（Root 域判定，含插件内容/自属目录豁免）
D. is_user_data_path 语义（升级/备份跳过保留）
E. BACKUP_ITEMS 从用户数据清单派生且与原语义一致

运行：python tests/test_framework_manifest.py
"""
import json
import os
import sys

sys.path.insert(0, _PROJECT_ROOT)

from core import framework_manifest as FM
from core import selfcheck
from core import capabilities as C

results = []


def check(name, cond, detail=''):
    results.append((name, bool(cond), detail))


# ------------------------------ A. 清单一致性 ------------------------------
check("A1 selfcheck.CORE_FILES 复用 manifest",
      selfcheck.CORE_FILES is FM.CORE_FILES, '')
check("A2 selfcheck.CORE_DIRS 复用 manifest",
      selfcheck.CORE_DIRS is FM.CORE_DIRS, '')
from tools.update import USER_DATA_PATHS, path_is_user_data
check("A3 tools.update USER_DATA_PATHS 复用 manifest",
      USER_DATA_PATHS is FM.USER_DATA_PATHS, '')
check("A4 tools.update path_is_user_data 复用 manifest",
      path_is_user_data is FM.path_is_user_data, '')
from tools.backup import BACKUP_ITEMS
check("A5 tools.backup BACKUP_ITEMS 复用 manifest",
      BACKUP_ITEMS is FM.BACKUP_ITEMS, '')

# ------------------------------ B. 完整性 ------------------------------
miss = [f for f in FM.CORE_FILES if not os.path.exists(os.path.join(_PROJECT_ROOT, f))]
check("B1 CORE_FILES 全存在（%d 个）" % len(FM.CORE_FILES), not miss, 'missing=%s' % miss)
missd = [d for d in FM.CORE_DIRS if not os.path.isdir(os.path.join(_PROJECT_ROOT, d))]
check("B2 CORE_DIRS 全存在（%d 个）" % len(FM.CORE_DIRS), not missd, 'missing=%s' % missd)
check("B3 清单含新增 core/framework_manifest.py", 'core/framework_manifest.py' in FM.CORE_FILES, '')

# ------------------------------ C. is_framework_core_path 边界 ------------------------------
_core_yes = [('app.py',), ('global_var.py',), ('requirements.txt',), ('changelog.json',),
             ('core/network.py',), ('routes/admin.py',), ('static/css/main.css',),
             ('templates/admin/dashboard.html',), ('data/user_config.json',),
             ('data/frontend_tools.json',), ('plugins/status.json',), ('plugins/other.py',),
             ('plugins/base_plugin.py',)]
_core_no = [('templates/plugins/x/a.html',), ('templates/frontend_tools/x/',),
            ('plugins/data/x/y',), ('plugins/temp/z',), ('plugins/configs/a.json',),
            ('data/stats.json',), ('logs/x.log',), ('backups/x',), ('users/x',)]
for p in _core_yes:
    ok = FM.is_framework_core_path(p[0]) is True
    check("C 核心命中 %s" % p[0], ok, '')
for p in _core_no:
    ok = FM.is_framework_core_path(p[0]) is False
    check("C 核心豁免 %s" % p[0], ok, '')
check("C capabilities 委托 manifest 判定",
      C.is_framework_core_path('core/network.py') is True
      and C.is_framework_core_path('plugins/data/x/y') is False, '')

# ------------------------------ D. is_user_data_path ------------------------------
for p in [('data/x', True), ('data/stats.json', True), ('plugins/configs/a.json', True),
          ('plugins/data/b/y', True), ('plugins/temp/c', True), ('logs/x.log', True),
          ('.plugin_cache/x', True), ('workspace/x', True), ('temp/x', True),
          ('backups/x', True), ('users/x', True), ('plugins/status.json', True),
          ('frontend_tools.json', True), ('.version', True)]:
    ok = FM.is_user_data_path(p[0]) is p[1]
    check("D 用户数据 %s" % p[0], ok, '')
for p in [('core/network.py', False), ('app.py', False), ('routes/admin.py', False),
          ('static/x.css', False), ('plugins/auth.py', False), ('plugins/base_plugin.py', False),
          ('templates/admin/x.html', False)]:
    ok = FM.is_user_data_path(p[0]) is p[1]
    check("D 非用户数据 %s" % p[0], ok, '')

# ------------------------------ E. BACKUP_ITEMS ------------------------------
items = {src for src, _ in FM.BACKUP_ITEMS}
expect = {'data', 'plugins/configs', 'plugins/data', 'logs', 'plugins/status.json', 'themes'}  # themes: v4.20.1 归用户数据（升级/备份保留用户主题）
check("E1 BACKUP_ITEMS 与原语义一致", items == expect, 'got=%s' % sorted(items))
check("E2 纯临时目录不入备份", not (items & {'.plugin_cache', 'workspace', 'temp', 'backups', 'users', 'plugins/temp'}),
      '')

# ============ 汇总 ============
n_pass = sum(1 for _, c, _ in results if c)
n_fail = len(results) - n_pass
for name, c, detail in results:
    if not c:
        print("[FAIL] %s %s" % (name, detail))
print("\n==== 框架目录清单统一回归（v4.15.1）：共 %d 项，通过 %d，失败 %d ====" % (len(results), n_pass, n_fail))
sys.exit(1 if n_fail else 0)
