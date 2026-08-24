# -*- coding: utf-8 -*-
"""
Factory Reset（重置）工具：将部分/全部框架数据还原至安装初始状态。

重置范围（scope）：
- plugins        清除全部非内置插件（插件 .py / 描述文件 / 模板 / 静态资源 / 临时目录）
- frontend_tools 清除前端工具（清单 + 模板目录）
- stats_logs     清除调用统计（data/stats.json）与日志（logs/）
- sessions       清除登录会话（plugins/data/sessions.json）
- temp           清除运行产生的临时文件（.plugin_cache、__pycache__、temp/、plugins/temp/）
- builtin        重置内置插件配置（auth 恢复默认 admin/admin123）——仅 all 时执行

内置插件（global_var.BUILTIN_PLUGINS）在插件重置中受保护，不被删除。
删除操作逐项 try/except，返回成功/失败列表（受限环境删除失败不影响接口返回）。
"""
import json
import logging
import os
import shutil

import global_var

logger = logging.getLogger('flask.app')

ALL_SCOPES = ('plugins', 'frontend_tools', 'stats_logs', 'sessions', 'temp')


def _safe_remove(path: str, results: dict, label: str):
    """删除文件或目录并记录结果（try/except 容忍，删除失败不中断）"""
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.isfile(path):
            os.remove(path)
        else:
            return
        results['cleaned'].append(label)
    except Exception as e:
        results['failed'].append(f"{label}: {e}")


def _write_text(path: str, text: str, results: dict, label: str):
    """原子写入文本并记录结果（目录自动创建）"""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.tmp"
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(text)
        os.replace(tmp, path)
        results['cleaned'].append(label)
    except Exception as e:
        results['failed'].append(f"{label}: {e}")


def reset_custom_plugins(results: dict):
    """清除全部非内置插件（.py / 描述文件 / 模板 / 静态 / 临时目录）"""
    base = global_var.BASE_DIR
    plugin_dir = os.path.join(base, 'plugins')
    if not os.path.isdir(plugin_dir):
        return

    for fn in sorted(os.listdir(plugin_dir)):
        full = os.path.join(plugin_dir, fn)
        if fn.endswith('.py'):
            name = fn[:-3]
            if name in global_var.BUILTIN_PLUGINS or name in ('__init__', 'base_plugin'):
                continue
            _safe_remove(full, results, f'插件 {fn}')
        elif fn.endswith('.json'):
            name = fn[:-5]
            if name in global_var.BUILTIN_PLUGINS or name == 'status':
                continue
            _safe_remove(full, results, f'插件描述 {fn}')
        elif fn == 'temp' and os.path.isdir(full):
            # 清除非内置插件临时子目录
            for sub in sorted(os.listdir(full)):
                if sub in global_var.BUILTIN_PLUGINS:
                    continue
                _safe_remove(os.path.join(full, sub), results, f'插件临时 {sub}')

    # templates/plugins 非内置模板与静态资源
    tpl_root = os.path.join(base, 'templates', 'plugins')
    if os.path.isdir(tpl_root):
        for fn in sorted(os.listdir(tpl_root)):
            name = fn[:-5] if fn.endswith('.html') else fn
            if name in global_var.BUILTIN_PLUGINS:
                continue
            _safe_remove(os.path.join(tpl_root, fn), results, f'插件模板 {fn}')
        static_root = os.path.join(tpl_root, 'static')
        if os.path.isdir(static_root):
            for fn in sorted(os.listdir(static_root)):
                if fn in global_var.BUILTIN_PLUGINS:
                    continue
                _safe_remove(os.path.join(static_root, fn), results, f'插件静态 {fn}')


def reset_frontend_tools(results: dict):
    """清除前端工具（清单 + 模板目录）"""
    _write_text(global_var.FRONTEND_CONFIG_FILE, '[]', results, '前端工具清单')
    if os.path.isdir(global_var.FRONTEND_TEMPLATE_DIR):
        for fn in os.listdir(global_var.FRONTEND_TEMPLATE_DIR):
            _safe_remove(os.path.join(global_var.FRONTEND_TEMPLATE_DIR, fn), results, f'前端工具 {fn}')


def reset_stats_logs(results: dict):
    """清除调用统计与日志"""
    stats_path = os.path.join(global_var.BASE_DIR, 'data', 'stats.json')
    _write_text(stats_path, json.dumps(
        {'call_stats': {}, 'frontend_access_stats': {}}, ensure_ascii=False, indent=2
    ), results, '统计 data/stats.json')
    # 同步清空内存统计
    global_var.call_stats.clear()
    global_var.frontend_access_stats.clear()

    logs_dir = os.path.join(global_var.BASE_DIR, 'logs')
    if os.path.isdir(logs_dir):
        for fn in os.listdir(logs_dir):
            _safe_remove(os.path.join(logs_dir, fn), results, f'日志 {fn}')


def reset_sessions(results: dict):
    """清除登录会话"""
    sessions_file = os.path.join(global_var.BASE_DIR, 'plugins', 'data', 'sessions.json')
    _write_text(sessions_file, '{}', results, '登录会话')


def reset_temp(results: dict):
    """清除运行产生的临时文件（.plugin_cache、__pycache__、temp/、plugins/temp/）"""
    base = global_var.BASE_DIR

    cache_dir = os.path.join(base, '.plugin_cache')
    if os.path.isdir(cache_dir):
        for fn in os.listdir(cache_dir):
            _safe_remove(os.path.join(cache_dir, fn), results, f'缓存 {fn}')

    tmp_dir = os.path.join(base, 'temp')
    if os.path.isdir(tmp_dir):
        for fn in os.listdir(tmp_dir):
            _safe_remove(os.path.join(tmp_dir, fn), results, f'临时 {fn}')

    # 递归清理 __pycache__
    for root, dirs, files in os.walk(base):
        if '__pycache__' in dirs:
            _safe_remove(os.path.join(root, '__pycache__'), results,
                         f'缓存 {os.path.relpath(root, base)}/__pycache__')
            dirs.remove('__pycache__')


def reset_builtin_config(results: dict):
    """重置内置插件配置：auth 恢复默认（users 清空，加载时自动重建 admin/admin123）"""
    auth_cfg = os.path.join(global_var.BASE_DIR, 'plugins', 'configs', 'auth.json')
    try:
        with open(auth_cfg, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        cfg['users'] = []
        with open(auth_cfg, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        results['cleaned'].append('内置配置（auth 恢复默认）')
    except Exception as e:
        results['failed'].append(f'内置配置: {e}')


_SCOPE_FUNCS = {
    'plugins': reset_custom_plugins,
    'frontend_tools': reset_frontend_tools,
    'stats_logs': reset_stats_logs,
    'sessions': reset_sessions,
    'temp': reset_temp,
    'builtin': reset_builtin_config,
}


def factory_reset(scope) -> dict:
    """
    执行 Factory Reset。
    :param scope: 'all' 或 'plugins'/'frontend_tools'/'stats_logs'/'sessions'/'temp' 之一
                  或上述列表。
    :return: {'cleaned': [...], 'failed': [...]}
    """
    if scope == 'all':
        scopes = list(ALL_SCOPES) + ['builtin']
    elif isinstance(scope, str):
        scopes = [scope] if scope in ALL_SCOPES else []
    else:
        scopes = [s for s in scope if s in ALL_SCOPES]

    results = {'cleaned': [], 'failed': []}
    for s in scopes:
        try:
            _SCOPE_FUNCS[s](results)
        except Exception as e:
            results['failed'].append(f"{s}: {e}")
    logger.info(f"Factory Reset 执行范围 {scopes}，清理 {len(results['cleaned'])} 项，失败 {len(results['failed'])} 项",
                extra={'plugin': 'system'})
    return results
