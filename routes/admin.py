# -*- coding: utf-8 -*-
"""管理端路由：插件管理（列表/启用/禁用/卸载/更新/上传）、统计、日志、系统信息、管理页面"""
import logging
import os
import platform
import sys
import time
import uuid

from flask import jsonify, render_template, request

import global_var
from core.factory_reset import factory_reset
from core.package_sign import verify_package
from core.permission import admin_api
from core.plugin_cache import compute_directory_fingerprint, load_plugin_cache
from core.plugin_loader import load_plugins
from core.plugin_pack import (cleanup_plugin_data, cleanup_plugin_resources,
                              compare_versions, extract_plugin_pack, parse_plugin_pack)
from core.quota import invalidate_cache as invalidate_quota_cache
from core.plugin_status import load_plugin_status, save_plugin_status
from core.audit import log_audit
from core.utils import check_upload_size, secure_filename_cn
from core.plugin_scanner import scan_plugin_zip, should_block
from core.capabilities import cross_validate, read_pack_capabilities
from core.audit_hook import get_violations as get_audit_violations
from core.watcher import save_cache_internal

logger = logging.getLogger('flask.app')


def register(app):
    @app.route('/api/admin/plugins', methods=['GET'])
    @admin_api
    def get_all_plugins():
        """获取所有插件和前端工具列表（包含禁用状态），从内存注册表读取（不再每次请求扫描磁盘）"""
        all_plugins = [dict(t) for t in global_var.plugin_catalog]

        # 溯源：合并 status.json 中的来源/安装时间/版本历史（自定义插件安装/更新时写入）
        for p in all_plugins:
            _st = global_var.plugin_status.get(p.get('name'))
            if _st and isinstance(_st, dict):
                p['source'] = _st.get('source', '')
                p['install_time'] = _st.get('install_time', '')
                p['history'] = _st.get('history', [])

        # 前端工具：内存列表已含 name/title/author/description/version/category/permission/enabled/type
        for tool in global_var.frontend_tools:
            item = dict(tool)
            item['loaded'] = True
            item['dependencies'] = []
            item['require_framework_version'] = tool.get('require_framework_version', '')
            item['api_calls'] = global_var.frontend_access_stats.get(f"frontend:{tool['name']}", 0)
            all_plugins.append(item)

        return jsonify({"code": 200, "data": all_plugins})

    @app.route('/api/admin/quota', methods=['GET'])
    @admin_api
    def get_all_quota():
        """插件空间管理（v4.9.2）：按插件列配额/用量/剩余 + 全局总量"""
        from core import quota
        plugins = quota.all_plugins_quota()
        g_limit = quota.total_limit_mb()
        g_usage = quota._total_usage() / 1048576
        return jsonify({"code": 200, "data": {
            "plugins": plugins,
            "total": {"limit_mb": g_limit, "usage_mb": round(g_usage, 1),
                        "remaining_mb": None if not g_limit else round(max(0.0, g_limit - g_usage), 1)}
        }})

    # 全局插件调用入口
    @app.route('/api/admin/plugins/<plugin_name>/enable', methods=['POST'])
    @admin_api
    def enable_plugin(plugin_name):
        """启用插件"""
        global_var.plugin_status[plugin_name] = global_var.plugin_status.get(plugin_name, {})
        global_var.plugin_status[plugin_name]['enabled'] = True
        save_plugin_status()
        log_audit('插件启用', plugin_name, 'ok')

        # 增量更新缓存中的状态快照
        cache = load_plugin_cache()
        if cache:
            cache['status_snapshot'] = global_var.plugin_status
            _, cache['status_hash'] = load_plugin_status()
            save_cache_internal(cache)

        load_plugins()
        return jsonify({"code": 200, "message": f"插件 {plugin_name} 已启用"})

    @app.route('/api/admin/plugins/<plugin_name>/disable', methods=['POST'])
    @admin_api
    def disable_plugin(plugin_name):
        """禁用插件"""
        if plugin_name not in global_var.plugins:
            return jsonify({"code": 404, "message": "插件不存在"}), 404

        global_var.plugin_status[plugin_name] = global_var.plugin_status.get(plugin_name, {})
        global_var.plugin_status[plugin_name]['enabled'] = False
        save_plugin_status()
        log_audit('插件禁用', plugin_name, 'ok')

        # 增量更新缓存中的状态快照
        cache = load_plugin_cache()
        if cache:
            cache['status_snapshot'] = global_var.plugin_status
            _, cache['status_hash'] = load_plugin_status()
            save_cache_internal(cache)

        load_plugins()
        return jsonify({"code": 200, "message": f"插件 {plugin_name} 已禁用"})

    @app.route('/api/admin/plugins/<plugin_name>/uninstall', methods=['POST'])
    @admin_api
    def uninstall_plugin(plugin_name):
        """卸载插件（删除文件）"""
        plugin_file = os.path.join(global_var.BASE_DIR, 'plugins', f'{plugin_name}.py')
        if not os.path.exists(plugin_file):
            return jsonify({"code": 404, "message": "插件文件不存在"}), 404

        try:
            # 调用插件卸载钩子（若已加载），钩子异常不影响卸载流程
            _inst = global_var.plugins.get(plugin_name)
            if _inst is not None:
                try:
                    _inst.on_unload()
                    _inst.on_uninstall()
                except Exception as _he:
                    logger.warning(f"插件 {plugin_name} 卸载钩子执行异常: {_he}", extra={'plugin': 'system'})

            os.remove(plugin_file)

            # 清理插件包附带资源（模板/静态目录）
            cleanup_plugin_resources(plugin_name)

            # 删除配置文件
            config_file = os.path.join(global_var.PLUGIN_CONFIGS_DIR, f'{plugin_name}.json')
            if os.path.exists(config_file):
                os.remove(config_file)

            # 删除状态
            global_var.plugin_status.pop(plugin_name, None)
            save_plugin_status()
            log_audit('插件卸载', plugin_name, 'ok')

            # 增量更新缓存（移除已卸载插件的条目）
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
                    os.path.join(global_var.BASE_DIR, 'plugins')
                )
                cache['timestamp'] = time.time()
                save_cache_internal(cache)

            load_plugins()
            return jsonify({"code": 200, "message": f"插件 {plugin_name} 已卸载"})
        except Exception as e:
            return jsonify({"code": 500, "message": f"卸载失败: {str(e)}"}), 500

    @app.route('/api/admin/plugins/<plugin_name>/purge-data', methods=['POST'])
    @admin_api
    def purge_plugin_data(plugin_name):
        """清理单插件空间（v4.10 M6-Extra）：body {"scope": "temp"}（默认，临时目录）或 {"scope": "all"}（全部数据）
        - temp：plugins/temp/<name>/
        - all：plugins/data/<name>/ + plugins/temp/<name>/ + capabilities filesystem:write 声明目录
        不删除插件代码/模板/配置。"""
        plugin_file = os.path.join(global_var.BASE_DIR, 'plugins', f'{plugin_name}.py')
        if not os.path.exists(plugin_file):
            return jsonify({"code": 404, "message": "插件文件不存在"}), 404
        body = request.get_json(silent=True) or {}
        include_data = body.get('scope') == 'all'
        removed = cleanup_plugin_data(plugin_name, include_data=include_data)
        invalidate_quota_cache(plugin_name)
        log_audit('插件数据清理', plugin_name, 'ok', f"scope={'all' if include_data else 'temp'}")
        return jsonify({
            "code": 200,
            "message": f"已清理 {len(removed)} 项空间（{'全部数据' if include_data else '临时目录'}）",
            "cleaned": [os.path.relpath(p, global_var.BASE_DIR).replace(os.sep, '/') for p in removed],
        })

    @app.route('/api/admin/plugins/<plugin_name>/update', methods=['POST'])
    @admin_api
    def update_plugin(plugin_name):
        """更新插件包（.zip：plugin.json + 主.py + 可选 templates/static）"""
        if 'file' not in request.files:
            return jsonify({"code": 400, "message": "缺少插件包文件"}), 400

        file = request.files['file']
        if not file.filename.endswith('.zip'):
            return jsonify({"code": 400, "message": "必须上传 .zip 格式的插件包"}), 400

        # 包大小上限校验（超限返回 413）
        oversize = check_upload_size(file, global_var.PACKAGE_MAX_UPLOAD_SIZE)
        if oversize:
            return jsonify({
                "code": 413,
                "message": f"插件包大小超过限制 {global_var.PACKAGE_MAX_UPLOAD_SIZE // (1024 * 1024)}MB（实际约 {oversize // (1024 * 1024)}MB）"
            }), 413

        temp_filename = secure_filename_cn(file.filename)
        temp_path = os.path.join(global_var.UPLOAD_TEMP_DIR, temp_filename)
        # v4.9.2 兜底：确保上传临时目录存在（模块级已创建，此处防御其他调用路径）
        os.makedirs(global_var.UPLOAD_TEMP_DIR, exist_ok=True)
        file.save(temp_path)
        try:
            desc = parse_plugin_pack(temp_path)
            # 完整性校验（P2-4）
            vres = verify_package(temp_path, 'backend')
            if not vres['ok']:
                return jsonify({"code": 400, "message": vres['message']}), 400
            if vres.get('warn_only'):
                logger.warning(vres['message'], extra={'plugin': 'system'})
            # 校验包内插件名与目标一致
            if desc['name'] != plugin_name:
                return jsonify({
                    "code": 400,
                    "message": f"更新包插件名与当前插件不一致（包内: {desc['name']}，目标: {plugin_name}）"
                }), 400
            # 静态扫描门禁（v4.3.1）：更新同样过扫描
            scan_report, scan_err = _scan_gate(temp_path, '插件更新', desc['name'])
            if scan_err:
                return scan_err

            # 版本校验：新版本必须高于当前版本
            current_version = next(
                (p.get('version') for p in global_var.plugin_catalog if p.get('name') == plugin_name),
                None
            )
            new_version = desc.get('version')
            if current_version and new_version and compare_versions(str(new_version), str(current_version)) <= 0:
                return jsonify({
                    "code": 400,
                    "message": f"更新包版本必须高于当前版本（当前: {current_version}，更新包: {new_version}）"
                }), 400

            # 安全解压覆盖（含模板/静态资源）；meta_override 落盘对齐后的描述
            extract_plugin_pack(temp_path, plugin_name, meta_override=desc)
            load_plugins()
            logger.info(f"插件包 {plugin_name} 已更新至 v{new_version or '?'}", extra={'plugin': 'system'})
            # 溯源：追加版本历史
            _now = time.strftime('%Y-%m-%d %H:%M:%S')
            _prev = global_var.plugin_status.get(plugin_name, {})
            _hist = list(_prev.get('history', []))
            _hist.append({'version': str(new_version or '?'), 'time': _now, 'source': temp_filename})
            global_var.plugin_status[plugin_name] = {
                'enabled': _prev.get('enabled', True),
                'version': str(new_version or '?'),
                'source': temp_filename,
                'install_time': _prev.get('install_time', _now),
                'history': _hist,
            }
            save_plugin_status()
            log_audit('插件更新', plugin_name, 'ok', f"v{current_version}→v{new_version} 来源 {temp_filename}")
            resp = {"code": 200, "message": f"插件 {plugin_name} 已更新"}
            if scan_report is not None:
                resp['scan'] = scan_report['summary']
                if scan_report['scope']['paths_written'] or scan_report['scope']['network_endpoints']:
                    resp['scan_scope'] = scan_report['scope']
                _cr = scan_report.get('capabilities')
                if _cr:
                    resp['capabilities'] = {k: _cr[k] for k in
                                            ('declared', 'missing', 'suggested') if _cr.get(k) is not None}
            return jsonify(resp)
        except ValueError as e:
            return jsonify({"code": 400, "message": str(e)}), 400
        except Exception as e:
            logger.error(f"更新插件包失败: {str(e)}", extra={'plugin': 'system'})
            return jsonify({"code": 500, "message": f"更新失败: {str(e)}"}), 500
        finally:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                # 临时文件清理失败不影响业务（如运行环境禁止永久删除）
                pass

    def _scan_gate(temp_path, action, plugin_name):
        """静态扫描 + capabilities 交叉校验门禁（v4.3.1/v4.3.2）：返回 (scan_report|None, 错误响应|None)
        - PLUGIN_SCAN_MODE=off：跳过；report：仅报告（告警日志 + 响应附扫描/能力摘要）；
        - enforce：存在高风险 **或 capabilities 未声明行为** 即拒绝安装/更新，响应附完整报告。"""
        if global_var.PLUGIN_SCAN_MODE == 'off':
            return None, None
        report = scan_plugin_zip(temp_path)
        # capabilities 交叉校验（v4.3.2）：声明白名单 × 扫描行为范围
        caps = read_pack_capabilities(temp_path)
        cap_res = cross_validate(plugin_name, report, caps)
        report['capabilities'] = cap_res
        blocked = should_block(report) or not cap_res['ok']
        if global_var.PLUGIN_SCAN_MODE == 'enforce' and blocked:
            reasons = []
            if report['summary']['high']:
                reasons.append(f"静态扫描 {report['summary']['high']} 项高风险行为")
            if not cap_res['ok']:
                reasons.append(f"capabilities 未声明行为 {len(cap_res['missing'])} 项（{'; '.join(cap_res['missing'][:5])}）")
            log_audit(action, plugin_name, 'blocked',
                      "；".join(reasons) + "，PLUGIN_SCAN_MODE=enforce 拒绝")
            return report, (jsonify({
                "code": 400,
                "message": "；".join(reasons) + f"（PLUGIN_SCAN_MODE=enforce 已拒绝{action}）",
                "scan_report": report,
            }), 400)
        if report['summary']['high'] > 0:
            logger.warning(
                f"插件包静态扫描发现 {report['summary']['high']} 项高风险（report 模式放行）: {plugin_name}",
                extra={'plugin': 'system'})
        if not cap_res['ok']:
            logger.warning(
                f"插件包 capabilities 未声明行为 {len(cap_res['missing'])} 项（report 模式放行）: {plugin_name}",
                extra={'plugin': 'system'})
        return report, None

    @app.route('/api/admin/plugins/upload', methods=['POST'])
    @admin_api
    def upload_new_plugin():
        """上传新插件包（.zip：plugin.json + 主.py + 可选 templates/static）

        v4.10 安装前能力确认（Accessibility）：
        - form 带 preview=1：仅解析并返回能力预览（插件信息/依赖/capabilities/扫描摘要），不安装；
        - form 带 confirm=1&preview_id=xxx：按预览文件执行安装；
        - 无参数：保持旧行为直接安装（兼容旧前端）。
        """
        is_preview = request.form.get('preview') == '1'
        is_confirm = request.form.get('confirm') == '1'

        if is_confirm:
            # 确认安装：复用预览阶段保存的临时包
            preview_id = request.form.get('preview_id', '')
            temp_path = os.path.join(global_var.UPLOAD_TEMP_DIR, preview_id)
            if (not preview_id or not preview_id.startswith('preview_')
                    or not os.path.isfile(temp_path)):
                return jsonify({"code": 400, "message": "预览文件不存在或已失效，请重新上传"}), 400
            temp_filename = preview_id
        else:
            if 'file' not in request.files:
                return jsonify({"code": 400, "message": "缺少插件包文件"}), 400
            file = request.files['file']
            if not file.filename.endswith('.zip'):
                return jsonify({"code": 400, "message": "必须上传 .zip 格式的插件包"}), 400
            # 包大小上限校验（超限返回 413）
            oversize = check_upload_size(file, global_var.PACKAGE_MAX_UPLOAD_SIZE)
            if oversize:
                return jsonify({
                    "code": 413,
                    "message": f"插件包大小超过限制 {global_var.PACKAGE_MAX_UPLOAD_SIZE // (1024 * 1024)}MB（实际约 {oversize // (1024 * 1024)}MB）"
                }), 413
            temp_filename = secure_filename_cn(file.filename)
            temp_path = os.path.join(global_var.UPLOAD_TEMP_DIR, temp_filename)
            file.save(temp_path)
            if is_preview:

                # 预览阶段：移到独立 preview_ 前缀临时文件，避免与普通上传混淆
                pv_name = 'preview_' + uuid.uuid4().hex + '.zip'
                pv_path = os.path.join(global_var.UPLOAD_TEMP_DIR, pv_name)
                os.replace(temp_path, pv_path)
                temp_filename, temp_path = pv_name, pv_path

        try:
            # 解析描述文件并校验主插件文件
            desc = parse_plugin_pack(temp_path)

            # ==================== v4.10 安装前能力预览（仅解析，不安装） ====================
            if is_preview:
                vres = verify_package(temp_path, 'backend')
                if not vres['ok']:
                    return jsonify({"code": 400, "message": vres['message']}), 400
                scan_report, scan_err = _scan_gate(temp_path, '插件安装预览', desc['name'])
                if scan_err:
                    return scan_err
                caps = {}
                try:
                    from core.plugin_scanner import read_pack_capabilities
                    caps = read_pack_capabilities(temp_path) or {}
                except Exception:
                    pass
                cap_res = (scan_report or {}).get('capabilities') or {}
                preview = {
                    'name': desc['name'],
                    'version': str(desc.get('version', '?')),
                    'title': desc.get('title', desc['name']),
                    'author': desc.get('author', '佚名'),
                    'permission': desc.get('permission', 'user'),
                    'category': desc.get('category', '其他工具'),
                    'description': desc.get('description', ''),
                    'dependencies': desc.get('dependencies', []),
                    'pip_dependencies': desc.get('pip_dependencies', []),
                    'capabilities': caps,
                    'cap_ok': bool(cap_res.get('ok', True)),
                    'cap_missing': cap_res.get('missing', []) or [],
                    'scan_summary': (scan_report or {}).get('summary', {}),
                    'scan_scope': (scan_report or {}).get('scope', {}),
                }
                return jsonify({"code": 200, "preview": preview, "preview_id": temp_filename})

            # 完整性校验（P2-4 方案C：manifest 哈希清单 + 可选签名）
            vres = verify_package(temp_path, 'backend')
            if not vres['ok']:
                return jsonify({"code": 400, "message": vres['message']}), 400
            if vres.get('warn_only'):
                logger.warning(vres['message'], extra={'plugin': 'system'})
            # 静态扫描门禁（v4.3.1）：enforce 高风险拒绝 / report 附摘要
            scan_report, scan_err = _scan_gate(temp_path, '插件安装', desc['name'])
            if scan_err:
                return scan_err
            plugin_name = desc['name']
            plugin_file = os.path.join(global_var.BASE_DIR, 'plugins', f'{plugin_name}.py')

            if os.path.exists(plugin_file):
                return jsonify({"code": 400, "message": f"插件 {plugin_name} 已存在，如需更新请使用更新功能"}), 400

            # 安全解压到对应位置（含模板/静态资源）；meta_override 落盘对齐后的描述
            extract_plugin_pack(temp_path, plugin_name, meta_override=desc)
            # 自动重载插件
            load_plugins()
            logger.info(f"新插件包 {plugin_name} v{desc.get('version', '?')} 已上传并加载", extra={'plugin': 'system'})
            # 溯源：记录来源/安装时间/版本历史（与启用状态共存于 status.json）
            _now = time.strftime('%Y-%m-%d %H:%M:%S')
            global_var.plugin_status[plugin_name] = {
                'enabled': True,
                'version': str(desc.get('version', '?')),
                'source': temp_filename,
                'install_time': _now,
                'history': [{'version': str(desc.get('version', '?')), 'time': _now, 'source': temp_filename}],
            }
            save_plugin_status()
            log_audit('插件安装', plugin_name, 'ok', f"v{desc.get('version', '?')} 来源 {temp_filename}")
            # 确认安装成功 → 清理预览临时文件
            if is_confirm:
                try:
                    if temp_filename.startswith('preview_') and os.path.isfile(temp_path):
                        os.remove(temp_path)
                except Exception:
                    pass
            resp = {"code": 200, "message": f"插件 {plugin_name} 上传成功，已自动加载"}
            if scan_report is not None:
                resp['scan'] = scan_report['summary']
                if scan_report['scope']['paths_written'] or scan_report['scope']['network_endpoints']:
                    resp['scan_scope'] = scan_report['scope']
                _cr = scan_report.get('capabilities')
                if _cr:
                    resp['capabilities'] = {k: _cr[k] for k in
                                            ('declared', 'missing', 'suggested') if _cr.get(k) is not None}
            return jsonify(resp)
        except ValueError as e:
            # 校验类错误：清理可能残留的解压文件
            try:
                if 'plugin_name' in dir():
                    _pn = locals().get('plugin_name')
                    if _pn:
                        _pf = os.path.join(global_var.BASE_DIR, 'plugins', f'{_pn}.py')
                        if os.path.exists(_pf):
                            os.remove(_pf)
                        cleanup_plugin_resources(_pn)
            except Exception:
                # 清理失败不阻断错误信息返回
                pass
            return jsonify({"code": 400, "message": str(e)}), 400
        except Exception as e:
            logger.error(f"上传插件包失败: {str(e)}", extra={'plugin': 'system'})
            return jsonify({"code": 500, "message": f"上传失败: {str(e)}"}), 500
        finally:
            try:
                # preview/confirm 两段式：preview 文件需保留到 confirm 阶段，
                # confirm 成功后在业务内显式清理；仅普通上传在此兜底清理
                if not is_preview and not is_confirm and os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                # 临时文件清理失败不影响业务（如运行环境禁止永久删除）
                pass

    @app.route('/api/admin/factory-reset', methods=['POST'])
    @admin_api
    def factory_reset_api():
        """Factory Reset：部分/全部还原至安装初始状态
        body: {"scope": "all"} 或 {"scope": ["plugins", "frontend_tools", "stats_logs", "sessions", "temp"]}
        """
        data = request.get_json(silent=True) or {}
        scope = data.get('scope', 'all')
        if isinstance(scope, (list, tuple)) and not scope:
            return jsonify({"code": 400, "message": "scope 不能为空列表"}), 400
        results = factory_reset(scope)
        # 重置后重载插件（内置插件按默认配置重新加载）
        try:
            load_plugins()
        except Exception as e:
            logger.error(f"Factory Reset 后重载插件失败: {str(e)}", extra={'plugin': 'system'})
        log_audit('工厂重置', str(scope), 'ok',
                  f"清理 {len(results['cleaned'])} 项，失败 {len(results['failed'])} 项")
        return jsonify({
            "code": 200,
            "data": results,
            "message": "重置完成",
        })

    @app.route('/api/admin/audit', methods=['GET'])
    @admin_api
    def get_audit_api():
        """获取审计日志（最近操作记录，倒序）"""
        from core.audit import get_audit_logs
        lines_raw = request.args.get('lines', '50')
        try:
            lines = int(lines_raw)
            lines = min(max(lines, 1), 500)
        except (TypeError, ValueError):
            lines = 50
        return jsonify({"code": 200, "data": get_audit_logs(lines)})

    @app.route('/api/admin/stats', methods=['GET'])
    @admin_api
    def get_stats():
        """获取调用统计"""
        total_api_calls = sum(global_var.call_stats.values())
        total_frontend_access = sum(global_var.frontend_access_stats.values())

        return jsonify({
            "code": 200,
            "data": {
                "total_plugins": len(global_var.plugins),
                "total_plugins_catalog": len(global_var.plugin_catalog),
                "total_frontend_tools": len(global_var.frontend_tools),
                "total_api_calls": total_api_calls,
                "total_frontend_access": total_frontend_access,
                "total_calls": total_api_calls + total_frontend_access,
                "api_call_details": global_var.call_stats,
                "frontend_access_details": global_var.frontend_access_stats,
                "audit_violations": get_audit_violations()
            }
        })

    @app.route('/api/admin/logs', methods=['GET'])
    @admin_api
    def get_logs():
        """获取最新日志"""
        # 阶段二-B：level 白名单化（仅允许标准日志级别，非法值回退 info，同时消除日志文件路径拼接的路径遍历风险）
        level = request.args.get('level', 'info').lower()
        _ALLOWED_LOG_LEVELS = ('debug', 'info', 'warning', 'error', 'critical')
        if level not in _ALLOWED_LOG_LEVELS:
            level = 'info'
        # lines 参数安全转换（非数字/越界回退默认 100）
        try:
            lines = int(request.args.get('lines', 100))
            if lines < 1:
                lines = 100
        except (TypeError, ValueError):
            lines = 100
        plugin = request.args.get('plugin', None)

        # 日志文件名映射：app.log 记录 INFO+，error.log 记录 ERROR+
        # （修复：此前按 level.log 读取但实际文件名是 app.log/error.log，导致日志页恒为空）
        _LEVEL_FILE = {
            'debug': ('app.log', None),
            'info': ('app.log', None),
            'warning': ('app.log', 'WARNING'),
            'error': ('error.log', None),
            'critical': ('error.log', 'CRITICAL'),
        }
        filename, level_marker = _LEVEL_FILE[level]
        log_file = os.path.join(global_var.LOG_DIR, filename)
        if not os.path.exists(log_file):
            return jsonify({"code": 200, "data": []})

        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                filtered = all_lines[-lines:] if len(all_lines) > lines else all_lines

                # 按级别标记二次过滤（如 warning 从 app.log 中筛出 WARNING 行）
                if level_marker:
                    filtered = [line for line in filtered if f' - {level_marker} - ' in line]

                if plugin:
                    filtered = [line for line in filtered if f'[{plugin}]' in line]

                return jsonify({"code": 200, "data": filtered})
        except Exception as e:
            return jsonify({"code": 500, "message": f"读取日志失败: {str(e)}"}), 500

    # ---------- 系统信息接口 ----------
    @app.route('/api/admin/system/info', methods=['GET'])
    @admin_api
    def get_system_info():
        """获取系统信息（框架/Python/平台/目录/统计概览），供管理后台展示"""
        total_api_calls = sum(global_var.call_stats.values())
        total_frontend_access = sum(global_var.frontend_access_stats.values())
        info = {
            "framework_version": global_var.FRAMEWORK_VERSION,
            "system_name": global_var.get_user_config().get("SYSTEM_NAME") or global_var.PROJECT_NAME,
            "system_version": global_var.get_user_config().get("SYSTEM_VERSION_LABEL") or ("v" + global_var.FRAMEWORK_VERSION),
            "project_name": global_var.PROJECT_NAME,
            "project_author": global_var.PROJECT_AUTHOR,
            "project_github": global_var.PROJECT_GITHUB,
            "project_slogan": global_var.PROJECT_SLOGAN,
            "builtin_plugins": list(global_var.BUILTIN_PLUGINS),
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "base_dir": global_var.BASE_DIR,
            "host": os.environ.get('FLASKTOOLKIT_HOST', '127.0.0.1').strip() or '127.0.0.1',
            "debug": bool(global_var.app and global_var.app.debug),
            "total_plugins": len(global_var.plugins),
            "total_plugins_catalog": len(global_var.plugin_catalog),
            "total_frontend_tools": len(global_var.frontend_tools),
            "total_api_calls": total_api_calls,
            "total_frontend_access": total_frontend_access,
            "total_calls": total_api_calls + total_frontend_access
        }
        return jsonify({"code": 200, "data": info})

    # ---------- 网络与访问（v4.11 Reachability） ----------

    @app.route('/api/admin/network', methods=['GET'])
    @admin_api
    def get_network_info():
        """获取网络与访问信息：绑定地址/可达地址/mDNS 状态/配置（v4.11 M3）"""
        from core import network as net_mod
        from core import mdns as mdns_mod
        ucfg = global_var.get_user_config()
        mdns_on = bool(ucfg.get('MDNS_ENABLED'))
        info = {
            'hostname': net_mod.get_hostname(),
            'binding_host': net_mod.get_binding_host(),
            'effective_port': net_mod.get_effective_port(),
            'scheme': net_mod.get_scheme(),
            'lan_addresses': net_mod.get_lan_addresses(),
            'access_urls': net_mod.get_access_urls(),
            'ip_watch_interval': int(ucfg.get('IP_WATCH_INTERVAL') or 30),
            'ip_watch': ip_watcher_status(),
            'mdns': {
                'enabled': mdns_on,
                'hostname': net_mod.get_mdns_hostname(),
                'url': net_mod.get_mdns_url() if mdns_on else None,
                'available': mdns_mod.available(),
                'active': mdns_mod.is_active(),
                'error': None if mdns_mod.available() else 'mDNS 需要可选依赖 zeroconf，请执行 pip install zeroconf 后重启启用',
            },
        }
        return jsonify({'code': 200, 'data': info})

    @app.route('/api/admin/network/config', methods=['POST'])
    @admin_api
    def update_network_config():
        """更新网络配置（v4.11）：HOST（0.0.0.0=共享局域网）/ MDNS_ENABLED / MDNS_HOSTNAME / IP_WATCH_INTERVAL

        写 data/user_config.json（同 tools/config.py 模式）；HOST/MDNS_ENABLED 需重启生效。"""
        import json
        from core import network as net_mod
        body = request.get_json(silent=True) or {}
        allowed = {'HOST', 'MDNS_ENABLED', 'MDNS_HOSTNAME', 'IP_WATCH_INTERVAL'}
        updates = {k: v for k, v in body.items() if k in allowed}
        if not updates:
            return jsonify({'code': 400, 'message': '无可更新配置项'}), 400

        # 类型与取值校验
        if 'HOST' in updates:
            host = str(updates['HOST']).strip()
            if host not in ('0.0.0.0', '127.0.0.1', '::') and not _looks_like_ip(host):
                return jsonify({'code': 400, 'message': f'HOST 需为 IP 地址或 0.0.0.0：{host}'}), 400
            updates['HOST'] = host
        if 'MDNS_ENABLED' in updates:
            updates['MDNS_ENABLED'] = bool(updates['MDNS_ENABLED'])
        if 'MDNS_HOSTNAME' in updates:
            name = str(updates['MDNS_HOSTNAME']).strip().replace('.local', '').lower()
            import re as _re
            if not _re.fullmatch(r'[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?', name or '_'):
                return jsonify({'code': 400, 'message': 'mDNS 主机名需为字母数字与短横线（如 mybox）'}), 400
            updates['MDNS_HOSTNAME'] = name
        if 'IP_WATCH_INTERVAL' in updates:
            try:
                interval = int(updates['IP_WATCH_INTERVAL'])
            except (TypeError, ValueError):
                return jsonify({'code': 400, 'message': 'IP_WATCH_INTERVAL 需为整数秒'}), 400
            if interval < 0 or interval > 3600:
                return jsonify({'code': 400, 'message': 'IP_WATCH_INTERVAL 范围 0-3600 秒'}), 400
            updates['IP_WATCH_INTERVAL'] = interval

        # 写 user_config.json 并重载（沿用 tools/config.py 的 _load_file/_save_file 模式）
        try:
            cfg_path = global_var.USER_CONFIG_FILE
            data = {}
            if os.path.exists(cfg_path):
                with open(cfg_path, encoding='utf-8') as f:
                    loaded = json.load(f)
                    data = loaded if isinstance(loaded, dict) else {}
            data.update(updates)
            os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
            with open(cfg_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            global_var.load_user_config()
        except Exception as e:
            return jsonify({'code': 500, 'message': f'配置写入失败: {e}'}), 500

        restart_keys = [k for k in updates if k in ('HOST', 'MDNS_ENABLED', 'MDNS_HOSTNAME')]
        detail = ', '.join(f'{k}={updates[k]}' for k in updates)
        log_audit('网络配置', ', '.join(updates.keys()), 'ok', detail)
        return jsonify({
            'code': 200,
            'message': '配置已保存' + ('，重启后生效' if restart_keys else ''),
            'updated': list(updates.keys()),
            'restart_required': bool(restart_keys),
        })

    def ip_watcher_status() -> dict:
        """IP 变化检测状态（v4.11 M4；import 放函数内避免模块级耦合）。"""
        try:
            from core import ip_watcher
            return ip_watcher.get_status()
        except Exception:
            return {'enabled': False, 'interval': 0, 'last_change_ts': None, 'last_change_detail': None}

    def _looks_like_ip(host: str) -> bool:
        """粗略校验 IPv4/IPv6 地址形态（HOST 配置用）。"""
        if ':' in host:
            return True  # IPv6 形态
        parts = host.split('.')
        return len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)

    # ---------- 版本更新检查接口（v4.8.0，F1） ----------
    @app.route('/api/admin/update/check', methods=['POST'])
    @admin_api
    def admin_update_check():
        """手动触发版本检查（force 刷新）；返回最新版本信息与是否有更新。
        数据源由 UPDATE_FEED_URL 指定（默认 GitHub changelog.json，内网可指向镜像）。"""
        try:
            from core.update_checker import check_for_update, is_newer
            _payload = request.get_json(silent=True) or {}
            info = check_for_update(force=bool(_payload.get("force")))
            current = global_var.FRAMEWORK_VERSION
            if info is None or not info.latest_version:
                return jsonify({"code": 200, "data": {
                    "checked": False,
                    "message": "检查失败：无法访问更新数据源（网络/格式），可查看日志",
                    "current_version": current,
                }})
            has_update = is_newer(info.latest_version, current)
            return jsonify({"code": 200, "data": {
                "checked": True,
                "current_version": current,
                "latest_version": info.latest_version,
                "published_at": info.published_at,
                "download_url": info.download_url,
                "changes": info.changes,
                "has_update": has_update,
                "checked_at": info.checked_at,
            }})
        except Exception as e:
            return jsonify({"code": 500, "message": f"版本检查异常: {e}"}), 500

    # ---------- 管理后台页面路由（均受管理员权限保护；auth 未安装时全放行） ----------
    def _admin_page(template, active_page, **extra):
        """管理页面通用渲染：注入 active_page 供 base.html 高亮导航"""
        total_api_calls = sum(global_var.call_stats.values())
        total_frontend_access = sum(global_var.frontend_access_stats.values())
        stats = {
            "total_plugins": len(global_var.plugins),
            "total_plugins_catalog": len(global_var.plugin_catalog),
            "total_frontend_tools": len(global_var.frontend_tools),
            "total_api_calls": total_api_calls,
            "total_frontend_access": total_frontend_access,
            "total_calls": total_api_calls + total_frontend_access
        }
        ctx = {"active_page": active_page, "stats": stats}
        ctx.update(extra)
        return render_template(template, **ctx)

    @app.route('/admin/dashboard')
    @admin_api
    def admin_dashboard():
        """管理后台：仪表盘（系统概览）"""
        return _admin_page('admin/dashboard.html', 'dashboard')

    @app.route('/admin/plugins')
    @admin_api
    def admin_plugins():
        """管理后台：插件管理页面"""
        return _admin_page('admin/plugins.html', 'plugins')

    @app.route('/admin/logs')
    @admin_api
    def admin_logs():
        """管理后台：日志查看页面"""
        return _admin_page('admin/logs.html', 'logs')

    @app.route('/admin/stats')
    @admin_api
    def admin_stats():
        """管理后台：统计页面"""
        return _admin_page('admin/stats.html', 'stats')

    @app.route('/admin/system')
    @admin_api
    def admin_system():
        """管理后台：系统管理（Factory Reset / 系统信息）"""
        return _admin_page('admin/system.html', 'system')

    @app.route('/admin/network')
    @admin_api
    def admin_network():
        """管理后台：网络与访问（v4.11 Reachability，共享入口）"""
        return _admin_page('admin/network.html', 'network')

    @app.route('/debug/plugin-list')
    def debug_plugin_list():
        return jsonify({
            "plugin_count": len(global_var.plugins),
            "plugins": list(global_var.plugins.keys())
        })
