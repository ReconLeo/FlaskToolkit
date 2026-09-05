# -*- coding: utf-8 -*-
"""插件数据配额回归（v4.9.0 防恶意写盘）：路径判定/用量统计/超限拒绝/observe 记录/TTL/禁用"""
import io
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import global_var
from core import audit_hook
from core import capabilities as caps_mod

_PASS = 0
_FAIL = 0


def check(name, cond, debug=''):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  ✓ {name}")
    else:
        _FAIL += 1
        print(f"  ✗ {name}{' | ' + str(debug) if debug else ''}")


# ---------- 隔离环境：monkeypatch BASE_DIR 到临时目录 ----------
_tmp = tempfile.mkdtemp(prefix='ftk_data_limit_')
_orig_base = global_var.BASE_DIR
global_var.BASE_DIR = _tmp
# 构造插件配额目录与文件
data_dir = os.path.join(_tmp, 'plugins', 'data', 'demo_plugin')
temp_dir = os.path.join(_tmp, 'plugins', 'temp', 'demo_plugin')
os.makedirs(data_dir, exist_ok=True)
os.makedirs(temp_dir, exist_ok=True)
os.makedirs(os.path.join(_tmp, 'plugins', 'data', 'other_plugin'), exist_ok=True)
with io.open(os.path.join(data_dir, 'a.bin'), 'wb') as f:
    f.write(b'x' * 1024)          # 1KB
with io.open(os.path.join(temp_dir, 't.tmp'), 'wb') as f:
    f.write(b'y' * 512)           # 512B

try:
    # ---------- 1. 路径判定 ----------
    check("data 目录内命中", audit_hook._in_plugin_quota_area('demo_plugin', os.path.join(data_dir, 'a.bin')))
    check("temp 目录内命中", audit_hook._in_plugin_quota_area('demo_plugin', os.path.join(temp_dir, 't.tmp')))
    check("data 目录本身命中", audit_hook._in_plugin_quota_area('demo_plugin', data_dir))
    check("其他插件 data 不命中", not audit_hook._in_plugin_quota_area('demo_plugin', os.path.join(_tmp, 'plugins', 'data', 'other_plugin', 'x.bin')))
    check("plugins/data 共享目录不命中", not audit_hook._in_plugin_quota_area('demo_plugin', os.path.join(_tmp, 'plugins', 'data')))
    check("框架 data/ 不命中", not audit_hook._in_plugin_quota_area('demo_plugin', os.path.join(_tmp, 'data', 'x.json')))
    check("归一化（反斜杠）命中", audit_hook._in_plugin_quota_area('demo_plugin', os.path.join(data_dir, 'sub', 'a.bin').replace('/', os.sep)))

    # ---------- 2. 用量统计 ----------
    audit_hook._data_dir_cache.pop('demo_plugin', None)
    usage = audit_hook._quota_usage('demo_plugin')
    check("用量统计 1536B", usage == 1536, f"got {usage}")

    # ---------- 3. 配置读取 ----------
    check("默认 50MB", audit_hook._data_limit_mb() == 50.0)

    # ---------- 4. 超限拒绝（enforce） ----------
    _orig_mode = audit_hook._MODE
    audit_hook._MODE = 'enforce'
    audit_hook._data_dir_cache['demo_plugin'] = (time.time(), 100 * 1048576)  # 模拟 100MB 已用
    try:
        audit_hook._check_data_quota('demo_plugin', os.path.join(data_dir, 'new.bin'))
        check("enforce 超限抛异常", False)
    except RuntimeError as e:
        check("enforce 超限抛异常", '数据配额超限' in str(e))
    # 未超限放行
    audit_hook._data_dir_cache['demo_plugin'] = (time.time(), 1024)
    try:
        audit_hook._check_data_quota('demo_plugin', os.path.join(data_dir, 'new.bin'))
        check("enforce 未超限放行", True)
    except RuntimeError:
        check("enforce 未超限放行", False)

    # ---------- 5. observe 记录不阻断 ----------
    audit_hook._MODE = 'observe'
    audit_hook._data_dir_cache['demo_plugin'] = (time.time(), 100 * 1048576)
    audit_hook._PENDING[:] = []
    try:
        audit_hook._check_data_quota('demo_plugin', os.path.join(data_dir, 'new.bin'))
        check("observe 超限不抛异常", True)
    except RuntimeError:
        check("observe 超限不抛异常", False)
    check("observe 记录 pending", any('配额超限' in d for _, _, _, d in audit_hook._PENDING))

    # ---------- 6. 0 禁用 ----------
    audit_hook._MODE = 'enforce'
    _orig_cfg = global_var.get_user_config
    global_var.get_user_config = lambda: {'PLUGIN_DATA_LIMIT_MB': 0}
    audit_hook._data_dir_cache['demo_plugin'] = (time.time(), 100 * 1048576)
    try:
        audit_hook._check_data_quota('demo_plugin', os.path.join(data_dir, 'new.bin'))
        check("limit=0 禁用不拦截", True)
    except RuntimeError:
        check("limit=0 禁用不拦截", False)
    global_var.get_user_config = _orig_cfg

    # ---------- 7. TTL 缓存刷新 ----------
    audit_hook._data_dir_cache['demo_plugin'] = (time.time() - 100, 999)   # 过期
    usage2 = audit_hook._quota_usage('demo_plugin')
    check("TTL 过期重新统计", usage2 == 1536, f"got {usage2}")
    audit_hook._MODE = _orig_mode
finally:
    global_var.BASE_DIR = _orig_base

print(f"\n==== 数据配额测试 共 {_PASS + _FAIL} 项，通过 {_PASS}，失败 {_FAIL} ====")
sys.exit(0 if _FAIL == 0 else 1)
