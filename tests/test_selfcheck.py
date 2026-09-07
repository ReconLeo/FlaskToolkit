# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""框架完整性自校验（core/selfcheck.py）回归（v4.15.0）

覆盖：
A. 核心文件清单完整性：v4.15.0 新增 Root 域服务层（plugin_admin）与插件更新源
   （plugin_updates）已被 routes/admin 顶层引用，必须登记进 CORE_FILES，
   避免全新环境启动时 admin 路由 import 崩却无自检拦截。
B. 时区数据探测：APScheduler 3.11 起用标准库 zoneinfo，Windows 依赖 tzdata；
   缺 tzdata 时 app.py 顶层创建 BackgroundScheduler(timezone=TIMEZONE) 会在
   import 阶段抛 ZoneInfoNotFoundError 使启动崩溃。selfcheck 需在自检阶段主动
   探测，非法/不可用时返回致命问题（而非静默通过、启动后才崩）。
C. 完整自检：当前环境文件齐全 + 依赖齐全 + 时区可解析时应通过（ok=True, fatal 为空）。
D. 首次运行标记逻辑：is_first_run / MARKER_FILE 基于 data/.initialized。

运行：python tests/test_selfcheck.py
"""
import os
import sys
import tempfile

REAL_BASE = _PROJECT_ROOT
sys.path.insert(0, REAL_BASE)

import core.selfcheck as sc

# ============ A. 核心文件清单完整性 ============
results = []

def case(name, cond, detail=""):
    results.append((name, bool(cond), detail))

# A1/A2：v4.15 新增服务层已登记（routes/admin 顶层引用，缺失致命）
case("A1 plugin_admin 已登记进 CORE_FILES",
     'core/plugin_admin.py' in sc.CORE_FILES,
     "routes/admin.py 顶层 from core.plugin_admin import ... 缺失则启动崩")
case("A2 plugin_updates 已登记进 CORE_FILES",
     'core/plugin_updates.py' in sc.CORE_FILES,
     "插件更新源服务层模块")
# A3：既有核心文件仍登记
for rel in ('app.py', 'core/plugin_loader.py', 'core/capabilities.py',
            'core/audit_hook.py', 'plugins/base_plugin.py'):
    case(f"A3 核心文件登记: {rel}", rel in sc.CORE_FILES, "")

# ============ B. 时区数据探测 ============
# B1：默认探测时区为 global_var.TIMEZONE（与 app.py 创建 scheduler 一致）
case("B1 _TZ_PROBE 与 TIMEZONE 一致",
     sc._TZ_PROBE == getattr(sys.modules.get('global_var'), 'TIMEZONE', 'Asia/Shanghai'),
     f"_TZ_PROBE={sc._TZ_PROBE!r}")

# B2：有效时区可解析（当前环境装有 tzdata / 系统 zoneinfo）
try:
    from zoneinfo import ZoneInfo
    ZoneInfo(sc._TZ_PROBE)
    _tz_ok = True
    _tz_detail = ""
except Exception as _e:
    _tz_ok = False
    _tz_detail = f"当前环境无法解析 {sc._TZ_PROBE!r}: {_e}"
case("B2 默认时区可解析", _tz_ok, _tz_detail)

# B3：非法时区 → _severity_check 返回"时区数据不可用"致命问题
_orig_probe = sc._TZ_PROBE
try:
    sc._TZ_PROBE = 'Invalid/No-Such-Zone'
    _sev = sc._severity_check()
finally:
    sc._TZ_PROBE = _orig_probe
case("B3 非法时区被致命捕获",
     any('时区数据不可用' in s for s in _sev),
     "缺 tzdata（Windows）或非法时区应在自检阶段报致命")

# B4：时区探测异常不会中断其他 fatal 收集（异常被捕获为致命项而非抛出）
case("B4 时区探测异常被转为致命项", isinstance(_sev, list), "")

# ============ C. 完整自检 ============
# C1：当前环境（文件齐全 + 依赖齐全 + tzdata 在）完整自检通过
_res = sc.run_selfcheck(verbose=False)
case("C1 完整自检通过", _res['ok'] and not _res['fatal'], f"fatal={_res['fatal']}")
case("C2 自检返回结构完整",
     set(_res.keys()) == {'ok', 'fatal', 'warnings', 'first_run'}, "")

# ============ D. 首次运行标记 ============
# D1：MARKER_FILE 指向 data/.initialized（基于 BASE_DIR）
case("D1 标记文件路径正确",
     sc.MARKER_FILE.endswith(os.path.join('data', '.initialized')),
     sc.MARKER_FILE)

# ============ 汇总 ============
n_pass = sum(1 for _, c, _ in results if c)
n_fail = len(results) - n_pass
print(f"\n==== 框架完整性自校验回归（v4.15.0）：共 {len(results)} 项，通过 {n_pass}，失败 {n_fail} ====")
if n_fail:
    for name, c, d in results:
        if not c:
            print(f"  [FAIL] {name}: {d}")
sys.exit(1 if n_fail else 0)
