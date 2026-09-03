# -*- coding: utf-8 -*-
"""框架完整性自校验

用途：
- 每次启动时快速校验框架核心文件/依赖是否完整（发现被误删/损坏/依赖缺失）。
- 首次启动（无 .initialized 标记）执行完整自检：核心文件/目录、第三方依赖、数据目录可写性，
  并在通过后写入首次运行标记。
- 严重问题（核心文件或依赖缺失）会让启动中止，避免运行在破损状态；可写性问题仅告警。

实现：
- CORE_FILES：框架核心文件清单（缺失 = 框架无法正常工作，致命）。
- CORE_DIRS：核心目录清单（缺失 = 致命）。
- REQUIRED_DEPS：第三方运行依赖（缺失 = 致命）。
- 首次启动标记：data/.initialized（记录首次完整自检通过时间）。
"""
import importlib
import os
import sys
import time

# 支持以脚本方式直接运行（python core/selfcheck.py）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import global_var

# 框架核心文件（相对 BASE_DIR）；缺失视为致命，阻止启动
CORE_FILES = [
    'app.py', 'global_var.py',
    # v4.5.0: 前端工具注册清单默认路径迁移至 data/frontend_tools.json（运行时配置不入库，
    # 缺失不致命：load_frontend_tools 容错为空列表，旧版根目录文件由 migrate_legacy_config 自动迁移）
    'routes/__init__.py', 'routes/admin.py', 'routes/frontend.py',
    'routes/public.py', 'routes/interceptor.py', 'routes/plugin.py',
    'routes/security.py',
    'core/utils.py', 'core/plugin_loader.py', 'core/plugin_pack.py',
    'core/factory_reset.py', 'core/audit.py', 'core/package_sign.py',
    'core/permission.py', 'core/stats.py', 'core/logging_setup.py',
    'core/frontend_tools.py', 'core/watcher.py', 'core/selfcheck.py',
    # v4.3.x-v4.4.0 安全强化新增模块
    'core/plugin_scanner.py', 'core/capabilities.py', 'core/audit_hook.py',
    'core/plugin_cache.py', 'core/plugin_status.py',
    'plugins/__init__.py', 'plugins/base_plugin.py',
    'plugins/auth.py', 'plugins/user_manage.py',
]

# 核心目录（缺失视为致命）
CORE_DIRS = ['routes', 'core', 'plugins', 'templates', 'documents', 'tools']

# 第三方运行依赖（缺失视为致命，启动前应 pip install -r requirements.txt）
REQUIRED_DEPS = ['flask', 'flask_cors', 'apscheduler', 'watchdog']

# 首次启动标记文件
MARKER_FILE = os.path.join(global_var.BASE_DIR, 'data', '.initialized')


def is_first_run() -> bool:
    """是否为首次运行（尚无首次启动标记）"""
    return not os.path.exists(MARKER_FILE)


def _severity_check() -> list:
    """致命问题（文件/目录/依赖缺失）"""
    issues = []
    for rel in CORE_FILES:
        if not os.path.exists(os.path.join(global_var.BASE_DIR, rel)):
            issues.append(f"核心文件缺失: {rel}")
    for d in CORE_DIRS:
        if not os.path.isdir(os.path.join(global_var.BASE_DIR, d)):
            issues.append(f"核心目录缺失: {d}")
    for dep in REQUIRED_DEPS:
        try:
            importlib.import_module(dep)
        except ImportError:
            issues.append(f"依赖缺失: {dep}（请执行 pip install -r requirements.txt）")
    return issues


def _writable_check() -> list:
    """数据目录可写性检查（非致命，仅告警）"""
    warnings = []
    data_dir = os.path.join(global_var.BASE_DIR, 'data')
    try:
        os.makedirs(data_dir, exist_ok=True)
        probe = os.path.join(data_dir, '.write_probe')
        with open(probe, 'w', encoding='utf-8') as f:
            f.write('ok')
        os.remove(probe)
    except Exception as e:
        warnings.append(f"数据目录不可写: {data_dir}（{e}），统计数据/审计日志可能无法落盘")
    return warnings


def run_selfcheck(verbose: bool = False) -> dict:
    """执行完整性自检。

    返回: {'ok': bool, 'fatal': [致命问题], 'warnings': [告警], 'first_run': bool}
    - ok=False 时调用方应中止启动。
    """
    first_run = is_first_run()
    fatal = _severity_check()
    warnings = _writable_check()
    ok = not fatal

    if ok and first_run:
        # 首次完整自检通过：写入标记
        try:
            os.makedirs(os.path.dirname(MARKER_FILE), exist_ok=True)
            with open(MARKER_FILE, 'w', encoding='utf-8') as f:
                f.write(time.strftime('%Y-%m-%d %H:%M:%S'))
        except Exception as e:
            warnings.append(f"首次启动标记写入失败: {e}")

    if verbose:
        status = "通过" if ok else "失败"
        print(f"[自检] 完整性自校验{status}（首次运行={first_run}）")
        for w in warnings:
            print(f"[自检] 警告: {w}")
    return {'ok': ok, 'fatal': fatal, 'warnings': warnings, 'first_run': first_run}


if __name__ == '__main__':
    # 命令行独立自检：python core/selfcheck.py
    res = run_selfcheck(verbose=True)
    for f in res['fatal']:
        print(f"[自检] 致命: {f}")
    print(f"[自检] 结果: {'通过' if res['ok'] else '失败'}（{'首次运行' if res['first_run'] else '非首次运行'}）")
    import sys
    sys.exit(0 if res['ok'] else 1)
