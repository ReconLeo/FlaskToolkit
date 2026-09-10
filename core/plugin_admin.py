# -*- coding: utf-8 -*-
"""插件管理服务层（v4.15，framework:manage 域的程序化接口）

从 routes/admin.py 提取的纯服务函数（入参为 zip_path / 插件名，而非 request 对象），
供两类调用方使用：
- 框架自身（管理员 HTTP 层 @admin_api）：actor=None，直接放行；
- 插件（声明 framework:manage 或 framework:core）：经 audit_hook 公共栈归因
  （locate_caller_plugin）自动识别调用者并校验授权，未声明抛 PluginAdminPermissionError——
  栈帧实据无法伪造，插件 A 无法冒用插件 B 的身份。

HTTP 路由（routes/admin.py）改调本层，行为保持不变；安装/更新仍过完整门禁
（完整性校验 + 静态扫描 + capabilities 交叉校验 + enforce 拒绝），更新源不绕过安全链路。
"""
import logging
import os
import time

import global_var
from core.audit import log_audit
from core.capabilities import check_framework, cross_validate, read_pack_capabilities
from core.plugin_cache import compute_directory_fingerprint, load_plugin_cache
from core.watcher import save_cache_internal
from core.plugin_loader import load_plugins
from core.package_sign import verify_package
from core.plugin_pack import (cleanup_plugin_data, cleanup_plugin_resources,
                              compare_versions, extract_plugin_pack, parse_plugin_pack)
from core.plugin_scanner import scan_plugin_zip, should_block
from core.plugin_status import load_plugin_status, save_plugin_status
from core.quota import invalidate_cache as invalidate_quota_cache

logger = logging.getLogger('flask.app')


class PluginAdminPermissionError(Exception):
    """插件调用插件管理服务但未声明 framework:manage"""


def _locate_caller():
    try:
        from core.audit_hook import locate_caller_plugin
        return locate_caller_plugin()
    except Exception:
        return None


def require_manage(actor=None):
    """权限守卫：返回实际调用者（None=框架自身）。
    actor 显式传入（测试用）优先；否则栈归因自动识别。"""
    caller = actor if actor is not None else _locate_caller()
    if caller is None:
        return None
    allowed, _ = check_framework(caller, 'manage')
    if not allowed:
        log_audit('插件管理越权', caller, 'blocked',
                  '未声明 framework:manage 调用插件管理服务')
        raise PluginAdminPermissionError(
            f'插件 {caller} 未声明 framework:manage，禁止程序化插件管理')
    return caller


def _actor_suffix(actor):
    return f'（调用方: {actor}）' if actor else ''


def _audit(action, plugin, result, detail, actor=None):
    log_audit(action, plugin, result, detail + _actor_suffix(actor))


def scan_gate(temp_path, action, plugin_name):
    """静态扫描 + capabilities 交叉校验门禁（v4.3.1/v4.3.2，自 routes/admin 提取）：
    返回 (report|None, error_message|None)；enforce 命中拒绝时 error_message 含原因。
    PLUGIN_SCAN_MODE=off 直接放行；report 模式高风险仅告警放行。"""
    if global_var.PLUGIN_SCAN_MODE == 'off':
        return None, None
    report = scan_plugin_zip(temp_path)
    caps = read_pack_capabilities(temp_path)
    cap_res = cross_validate(plugin_name, report, caps)
    report['capabilities'] = cap_res
    blocked = should_block(report) or not cap_res['ok']
    if global_var.PLUGIN_SCAN_MODE == 'enforce' and blocked:
        reasons = []
        if report['summary']['high']:
            reasons.append(f"静态扫描 {report['summary']['high']} 项高风险行为")
        if not cap_res['ok']:
            reasons.append(
                f"capabilities 未声明行为 {len(cap_res['missing'])} 项"
                f"（{'; '.join(cap_res['missing'][:5])}）")
        log_audit(action, plugin_name, 'blocked',
                  '；'.join(reasons) + '，PLUGIN_SCAN_MODE=enforce 拒绝')
        return report, '；'.join(reasons) + f'（PLUGIN_SCAN_MODE=enforce 已拒绝{action}）'
    if report['summary']['high'] > 0:
        logger.warning(
            f"插件包静态扫描发现 {report['summary']['high']} 项高风险（report 模式放行）: {plugin_name}",
            extra={'plugin': 'system'},
        )
    return report, None


def _scan_response_extra(report):
    """扫描附带回显（与既有 HTTP 响应体一致）：scan/scan_scope/capabilities"""
    extra = {}
    if report is not None:
        extra['scan'] = report['summary']
        if report['scope']['paths_written'] or report['scope']['network_endpoints']:
            extra['scan_scope'] = report['scope']
        _cr = report.get('capabilities')
        if _cr:
            extra['capabilities'] = {k: _cr[k] for k in
                                     ('declared', 'missing', 'suggested') if _cr.get(k) is not None}
    return extra


# ------------------------------ 状态类操作 ------------------------------

def _set_enabled(plugin_name, enabled, actor=None):
    """启用/禁用（共享实现）"""
    require_manage(actor)
    if enabled and plugin_name not in global_var.plugins:
        return False, '插件不存在'
    plugin_file = os.path.join(global_var.BASE_DIR, 'plugins', f'{plugin_name}.py')
    if not os.path.exists(plugin_file):
        return False, '插件文件不存在'
    global_var.plugin_status[plugin_name] = global_var.plugin_status.get(plugin_name, {})
    global_var.plugin_status[plugin_name]['enabled'] = enabled
    save_plugin_status()
    _audit('插件启用' if enabled else '插件禁用', plugin_name, 'ok', '', actor)
    # 增量更新缓存中的状态快照
    cache = load_plugin_cache()
    if cache:
        cache['status_snapshot'] = global_var.plugin_status
        _, cache['status_hash'] = load_plugin_status()
        save_cache_internal(cache)
    # v4.16：禁用时清理该插件订阅的事件（防止禁用后仍收到事件/绑定方法泄漏；重启用时 load_plugins 重新 on_load 订阅）
    if not enabled:
        try:
            _inst = global_var.plugins.get(plugin_name)
            if _inst is not None:
                _inst._cleanup_events()
        except Exception:
            pass
    load_plugins()
    return True, f'插件 {plugin_name} 已{"启用" if enabled else "禁用"}'


def _emit(event, **data):
    """v4.16 事件总线：发送事件，失败不影响业务。"""
    try:
        from core.events import events
        events.emit(event, **data)
    except Exception:
        pass


def enable(plugin_name, actor=None):
    ok, msg = _set_enabled(plugin_name, True, actor)
    if ok:
        _emit('plugin.enabled', plugin_name=plugin_name, actor=actor)
    return ok, msg


def disable(plugin_name, actor=None):
    ok, msg = _set_enabled(plugin_name, False, actor)
    if ok:
        _emit('plugin.disabled', plugin_name=plugin_name, actor=actor)
    return ok, msg


def uninstall(plugin_name, actor=None):
    """卸载插件（删除文件 + 附带资源 + 配置 + 状态）"""
    require_manage(actor)
    plugin_file = os.path.join(global_var.BASE_DIR, 'plugins', f'{plugin_name}.py')
    if not os.path.exists(plugin_file):
        return False, '插件文件不存在'
    # v4.16：反向依赖检查——若仍有插件依赖本插件，阻止卸载（避免产生悬空依赖）
    try:
        from core.plugin_deps import dep_name
        _dependents = [
            n for n, _p in global_var.plugins.items()
            if _p is not None and any(
                dep_name(d) == plugin_name
                for d in (getattr(_p, 'dependencies', None) or []))
        ]
        if _dependents:
            return False, (f'插件 {plugin_name} 正被依赖: {", ".join(_dependents)}，'
                           '请先卸载依赖方再卸载本插件')
    except Exception:
        pass
    try:
        _inst = global_var.plugins.get(plugin_name)
        if _inst is not None:
            try:
                _inst.on_unload()
                _inst.on_uninstall()
            except Exception as _he:
                logger.warning(f"插件 {plugin_name} 卸载钩子执行异常: {_he}",
                               extra={'plugin': 'system'})
        os.remove(plugin_file)
        cleanup_plugin_resources(plugin_name)
        config_file = os.path.join(global_var.PLUGIN_CONFIGS_DIR, f'{plugin_name}.json')
        if os.path.exists(config_file):
            os.remove(config_file)
        global_var.plugin_status.pop(plugin_name, None)
        save_plugin_status()
        _audit('插件卸载', plugin_name, 'ok', '', actor)
        cache = load_plugin_cache()
        if cache:
            cache['discovered_plugins'] = [
                info for info in cache['discovered_plugins']
                if info['name'] != plugin_name
            ]
            cache['fingerprints'].pop(plugin_name, None)
            cache['status_snapshot'] = global_var.plugin_status
            _, cache['status_hash'] = load_plugin_status()
            cache['dir_fingerprint'] = compute_directory_fingerprint(
                os.path.join(global_var.BASE_DIR, 'plugins'))
            cache['timestamp'] = time.time()
            save_cache_internal(cache)
        load_plugins()
        # v4.15.4：卸载后清理该插件统计残留（call_stats / daily_stats）
        try:
            from core.stats import purge_plugin_stats
            purge_plugin_stats(plugin_name)
        except Exception as _e:
            logger.warning(f'插件 {plugin_name} 统计清理失败: {_e}',
                           extra={'plugin': 'system'})
        _emit('plugin.uninstalled', plugin_name=plugin_name, actor=actor)
        return True, f'插件 {plugin_name} 已卸载'
    except Exception as e:
        return False, f'卸载失败: {str(e)}'


def purge_data(plugin_name, scope='temp', actor=None):
    """清理单插件空间：scope=temp（默认）| all（全部数据，含 filesystem:write 声明目录）"""
    require_manage(actor)
    plugin_file = os.path.join(global_var.BASE_DIR, 'plugins', f'{plugin_name}.py')
    if not os.path.exists(plugin_file):
        return False, '插件文件不存在'
    include_data = scope == 'all'
    removed = cleanup_plugin_data(plugin_name, include_data=include_data)
    invalidate_quota_cache(plugin_name)
    _audit('插件数据清理', plugin_name, 'ok', f"scope={'all' if include_data else 'temp'}", actor)
    return True, {
        'message': f"已清理 {len(removed)} 项空间（{'全部数据' if include_data else '临时目录'}）",
        'cleaned': [os.path.relpath(p, global_var.BASE_DIR).replace(os.sep, '/') for p in removed],
    }


# ------------------------------ 包操作（安装/更新） ------------------------------

def install_from_package(zip_path, plugin_name=None, actor=None, source_label=None):
    """从已就位的插件包安装新插件（zip_path 为本地路径）。
    返回 (ok, message, extra)；extra 含 scan 附带回显。权限：framework:manage。"""
    require_manage(actor)
    temp_path = zip_path
    desc = parse_plugin_pack(temp_path)
    vres = verify_package(temp_path, 'backend')
    if not vres['ok']:
        return False, vres['message'], {}
    if vres.get('warn_only'):
        logger.warning(vres['message'], extra={'plugin': 'system'})
    scan_report, scan_err = scan_gate(temp_path, '插件安装', desc['name'])
    if scan_err:
        return False, scan_err, {'scan_report': scan_report}
    name = plugin_name or desc['name']
    if name != desc['name']:
        return False, f'包内插件名 {desc["name"]} 与目标 {name} 不一致', {}
    plugin_file = os.path.join(global_var.BASE_DIR, 'plugins', f'{name}.py')
    if os.path.exists(plugin_file):
        return False, f'插件 {name} 已存在，如需更新请使用更新功能', {}
    extract_plugin_pack(temp_path, name, meta_override=desc)
    load_plugins()
    logger.info(f"新插件包 {name} v{desc.get('version', '?')} 已上传并加载",
                extra={'plugin': 'system'})
    _now = time.strftime('%Y-%m-%d %H:%M:%S')
    src = source_label or (os.path.basename(temp_path) if temp_path else '')
    global_var.plugin_status[name] = {
        'enabled': True,
        'version': str(desc.get('version', '?')),
        'source': src,
        'install_time': _now,
        'history': [{'version': str(desc.get('version', '?')), 'time': _now, 'source': src}],
    }
    save_plugin_status()
    _audit('插件安装', name, 'ok', f"v{desc.get('version', '?')} 来源 {src}", actor)
    _emit('plugin.installed', plugin_name=name, version=str(desc.get('version', '?')), actor=actor)
    extra = _scan_response_extra(scan_report)
    # v4.16：依赖预检——新插件声明的依赖插件未安装时附告警（不自动安装）
    _warn = []
    try:
        from core.plugin_deps import dep_name
        for _d in (desc.get('dependencies') or []):
            if dep_name(_d) not in global_var.plugins:
                _warn.append(_d)
    except Exception:
        pass
    if _warn:
        _msg = (f'插件 {name} 已安装，但依赖未安装: {", ".join(_warn)}，'
                '安装后暂无法加载，请先安装依赖')
    else:
        _msg = f'插件 {name} 已安装'
    return True, _msg, extra


def update_from_package(zip_path, plugin_name, actor=None, source_label=None):
    """更新已有插件（zip_path 为本地路径；包内插件名须与目标一致，版本须更高）。
    返回 (ok, message, extra)。权限：framework:manage。"""
    require_manage(actor)
    temp_path = zip_path
    desc = parse_plugin_pack(temp_path)
    vres = verify_package(temp_path, 'backend')
    if not vres['ok']:
        return False, vres['message'], {}
    if vres.get('warn_only'):
        logger.warning(vres['message'], extra={'plugin': 'system'})
    if desc['name'] != plugin_name:
        return False, f'更新包插件名与当前插件不一致（包内: {desc["name"]}，目标: {plugin_name}）', {}
    scan_report, scan_err = scan_gate(temp_path, '插件更新', desc['name'])
    if scan_err:
        return False, scan_err, {'scan_report': scan_report}
    current_version = next(
        (p.get('version') for p in global_var.plugin_catalog if p.get('name') == plugin_name),
        None)
    new_version = desc.get('version')
    if current_version and new_version and compare_versions(str(new_version), str(current_version)) <= 0:
        return False, (f'更新包版本必须高于当前版本'
                       f'（当前: {current_version}，更新包: {new_version}）'), {}
    extract_plugin_pack(temp_path, plugin_name, meta_override=desc)
    load_plugins()
    logger.info(f"插件包 {plugin_name} 已更新至 v{new_version or '?'}", extra={'plugin': 'system'})
    _now = time.strftime('%Y-%m-%d %H:%M:%S')
    src = source_label or (os.path.basename(temp_path) if temp_path else '')
    _prev = global_var.plugin_status.get(plugin_name, {})
    _hist = list(_prev.get('history', []))
    _hist.append({'version': str(new_version or '?'), 'time': _now, 'source': src})
    global_var.plugin_status[plugin_name] = {
        'enabled': _prev.get('enabled', True),
        'version': str(new_version or '?'),
        'source': src,
        'install_time': _prev.get('install_time', _now),
        'history': _hist,
    }
    save_plugin_status()
    _audit('插件更新', plugin_name, 'ok', f"v{current_version}→v{new_version} 来源 {src}", actor)
    extra = _scan_response_extra(scan_report)
    return True, f'插件 {plugin_name} 已更新', extra
