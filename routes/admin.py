# -*- coding: utf-8 -*-
"""管理端路由：插件管理（列表/启用/禁用/卸载/更新/上传）、统计、日志、系统信息、管理页面"""
import logging
import os
import platform
import sys
import time

from flask import jsonify, render_template, request

import global_var
from core.factory_reset import factory_reset
from core.package_sign import verify_package
from core.permission import admin_api
from core.plugin_cache import compute_directory_fingerprint, load_plugin_cache
from core.plugin_loader import load_plugins
from core.plugin_pack import (cleanup_plugin_resources, compare_versions,
                              extract_plugin_pack, parse_plugin_pack)
from core.plugin_status import load_plugin_status, save_plugin_status
from core.audit import log_audit
from core.utils import check_upload_size, secure_filename_cn
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
            return jsonify({"code": 200, "message": f"插件 {plugin_name} 已更新"})
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

    @app.route('/api/admin/plugins/upload', methods=['POST'])
    @admin_api
    def upload_new_plugin():
        """上传新插件包（.zip：plugin.json + 主.py + 可选 templates/static）"""
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

        try:
            # 解析描述文件并校验主插件文件
            desc = parse_plugin_pack(temp_path)
            # 完整性校验（P2-4 方案C：manifest 哈希清单 + 可选签名）
            vres = verify_package(temp_path, 'backend')
            if not vres['ok']:
                return jsonify({"code": 400, "message": vres['message']}), 400
            if vres.get('warn_only'):
                logger.warning(vres['message'], extra={'plugin': 'system'})
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
            return jsonify({"code": 200, "message": f"插件 {plugin_name} 上传成功，已自动加载"})
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
                if os.path.exists(temp_path):
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
                "frontend_access_details": global_var.frontend_access_stats
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

    @app.route('/debug/plugin-list')
    def debug_plugin_list():
        return jsonify({
            "plugin_count": len(global_var.plugins),
            "plugins": list(global_var.plugins.keys())
        })
