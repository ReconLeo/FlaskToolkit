# -*- coding: utf-8 -*-
"""前端工具路由：工具页面访问 + 上传/更新/卸载/启用/禁用管理 API"""
import json
import logging
import os
import time
import zipfile
import shutil

from flask import jsonify, render_template, request, send_from_directory

import global_var
from core.frontend_tools import load_frontend_tools
from core.permission import _check_permission, admin_api
from core.package_sign import verify_package
from core.plugin_pack import compare_versions
from core.stats import increment_frontend_access, save_stats
from core.audit import log_audit
from core.utils import check_upload_size, secure_filename_cn

logger = logging.getLogger('flask.app')

def _write_member(zf, member, dest):
    """从 zip 安全写入单个文件（自动建目录；写入前校验目标在项目目录内）"""
    base = os.path.abspath(global_var.BASE_DIR)
    dest_abs = os.path.abspath(dest)
    if not (dest_abs == base or dest_abs.startswith(base + os.sep)):
        raise ValueError(f"前端工具包解压目标超出项目目录: {dest}")
    os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
    with zf.open(member) as src, open(dest_abs, 'wb') as out:
        shutil.copyfileobj(src, out)


def safe_extract_frontend(zf, tool_name, target_dir, clean_static=False):
    """
    安全解压前端工具包（防 zip slip 路径穿越）：
    - <tool_name>.html  -> target_dir/
    - static/**         -> target_dir/static/<tool_name>/**
    返回 (html 路径, 静态文件列表)；缺少入口 html 时 html 路径为 None。
    """
    html_name = f"{tool_name}.html"
    html_path = None
    static_files = []

    # 更新时先清理旧静态资源目录，避免残留旧版本文件（清理失败不阻塞本次更新）
    if clean_static:
        static_root = os.path.join(target_dir, 'static', tool_name)
        if os.path.isdir(static_root):
            try:
                shutil.rmtree(static_root)
            except Exception as e:
                logger.warning(f"清理旧静态资源目录失败（不影响本次更新）: {static_root} - {e}")

    for member in zf.namelist():
        # zip 内路径统一用 '/' 分隔（不能用 os.path.normpath，Windows 下会把 '/' 转成 '\\'）
        normalized = member.replace('\\', '/')
        if normalized.endswith('/'):
            continue  # 目录条目

        # ---- zip slip 防护：拒绝 .. / 绝对路径 / 盘符路径 ----
        parts = normalized.split('/')
        if '..' in parts:
            raise ValueError(f"前端工具包包含非法路径（存在路径穿越风险）: {member}")
        if normalized.startswith('/') or (len(normalized) >= 2 and normalized[1] == ':'):
            raise ValueError(f"前端工具包包含绝对路径（非法）: {member}")

        if len(parts) == 1 and parts[0] == html_name:
            # 入口 html -> target_dir/
            dest = os.path.join(target_dir, parts[0])
            _write_member(zf, member, dest)
            html_path = dest
        elif parts[0] == 'static':
            # 静态资源 -> target_dir/static/<tool_name>/
            dest = os.path.join(target_dir, 'static', tool_name, *parts[1:])
            _write_member(zf, member, dest)
            static_files.append(dest)
        else:
            # config.json 等其它条目忽略
            continue

    return html_path, static_files


def cleanup_frontend_resources(tool_name):
    """
    删除前端工具关联的资源文件（卸载时调用）：
    - templates/frontend_tools/<name>.html 入口文件
    - templates/frontend_tools/static/<name>/ 静态资源目录
    返回删除路径列表。
    """
    removed = []
    html_path = os.path.join(global_var.FRONTEND_TEMPLATE_DIR, f"{tool_name}.html")
    if os.path.exists(html_path):
        os.remove(html_path)
        removed.append(html_path)
    static_dir = os.path.join(global_var.FRONTEND_TEMPLATE_DIR, 'static', tool_name)
    if os.path.isdir(static_dir):
        shutil.rmtree(static_dir)
        removed.append(static_dir)
    return removed


def register(app):
    # 前端工具路由注册（同步修改前端工具访问逻辑，增加禁用校验）
    @app.route('/frontend/<tool_name>')
    def frontend_tool(tool_name):
        tool = next((t for t in global_var.frontend_tools if t['name'] == tool_name), None)
        if not tool:
            logger.warning(f"尝试访问不存在的前端工具: {tool_name}", extra={'plugin': 'system'})
            return render_template('404.html', message="工具不存在"), 404

        # 新增禁用校验
        if not tool.get('enabled', True):
            logger.warning(f"尝试访问已禁用的前端工具: {tool_name}", extra={'plugin': 'system'})
            return render_template('403.html', message="该工具已被禁用"), 403

        # 访问控制：按 permission 字段校验（public/user/admin；auth 未安装时放行）
        permission_level = tool.get('permission') or 'public'
        auth_result = _check_permission(permission_level)
        if auth_result is not None:
            return auth_result

        logger.info(f"访问前端工具页面: {tool['title']}", extra={'plugin': f'frontend:{tool_name}'})
        increment_frontend_access(tool_name)

        return render_template(f'frontend_tools/{tool_name}.html', tool=tool)

    @app.route('/frontend-static/<tool_name>/<path:filename>')
    def frontend_static(tool_name, filename):
        """前端工具静态资源：/frontend-static/<tool_name>/<path> -> templates/frontend_tools/static/<tool_name>/<path>"""
        tool = next((t for t in global_var.frontend_tools if t['name'] == tool_name), None)
        if not tool:
            return render_template('404.html', message="工具不存在"), 404

        # 访问控制：静态资源与页面采用相同的权限校验
        permission_level = tool.get('permission') or 'public'
        auth_result = _check_permission(permission_level)
        if auth_result is not None:
            return auth_result

        static_dir = os.path.join(global_var.FRONTEND_TEMPLATE_DIR, 'static', tool_name)
        if not os.path.isdir(static_dir):
            return render_template('404.html', message="静态资源不存在"), 404
        return send_from_directory(static_dir, filename)

    @app.route('/api/admin/frontend/upload', methods=['POST'])
    @admin_api
    def upload_frontend_tool():
        """上传前端工具zip包"""
        if 'file' not in request.files:
            return jsonify({"code": 400, "message": "未上传文件"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"code": 400, "message": "文件名不能为空"}), 400

        if not file.filename.endswith('.zip'):
            return jsonify({"code": 400, "message": "仅支持zip格式包"}), 400

        # 包大小上限校验（超限返回 413）
        oversize = check_upload_size(file, global_var.PACKAGE_MAX_UPLOAD_SIZE)
        if oversize:
            return jsonify({
                "code": 413,
                "message": f"工具包大小超过限制 {global_var.PACKAGE_MAX_UPLOAD_SIZE // (1024 * 1024)}MB（实际约 {oversize // (1024 * 1024)}MB）"
            }), 413

        # 保存临时文件
        temp_filename = secure_filename_cn(file.filename)
        temp_path = os.path.join(global_var.UPLOAD_TEMP_DIR, temp_filename)
        file.save(temp_path)

        try:
            # 完整性校验（P2-4 方案C）
            vres = verify_package(temp_path, 'frontend')
            if not vres['ok']:
                return jsonify({"code": 400, "message": vres['message']}), 400
            if vres.get('warn_only'):
                logger.warning(vres['message'], extra={'plugin': 'system'})
            # 解压校验
            with zipfile.ZipFile(temp_path, 'r') as zf:
                # 检查是否存在config.json
                if 'config.json' not in zf.namelist():
                    return jsonify({"code": 400, "message": "工具包缺少config.json配置文件"}), 400

                # 读取配置
                with zf.open('config.json', 'r') as f:
                    try:
                        config = json.load(f)
                    except json.JSONDecodeError:
                        return jsonify({"code": 400, "message": "config.json格式错误"}), 400

                # 校验必填字段（更新为新要求）
                required_fields = ['name', 'version', 'category']
                for field in required_fields:
                    if field not in config:
                        return jsonify({"code": 400, "message": f"config.json缺少必填字段: {field}"}), 400

                tool_name = secure_filename_cn(config['name'])
                html_file = f"{tool_name}.html"

                # 检查是否存在对应html文件
                if html_file not in zf.namelist():
                    return jsonify({"code": 400, "message": f"工具包缺少入口文件: {html_file}"}), 400

                # 检查是否已存在同名工具
                exists = any(t['name'] == tool_name for t in global_var.frontend_tools)
                if exists:
                    return jsonify({"code": 400, "message": f"已存在同名工具: {tool_name}，请使用更新接口"}), 400

                # 框架版本校验（可选字段）：点分版本比较（修复字符串比较缺陷）
                if 'require_framework_version' in config:
                    if compare_versions(config['require_framework_version'], global_var.FRAMEWORK_VERSION) > 0:
                        return jsonify({
                            "code": 400,
                            "message": f"工具要求框架最低版本为 {config['require_framework_version']}，当前版本为 {global_var.FRAMEWORK_VERSION}"
                        }), 400

                # 安全解压 html + 静态资源（防 zip slip）
                safe_extract_frontend(zf, tool_name, global_var.FRONTEND_TEMPLATE_DIR)

                # 保存到全局配置（适配新字段）
                global_var.frontend_tools.append({
                    'name': tool_name,
                    'title': config.get('title', tool_name),  # 可选，缺省用name
                    'permission': config.get('permission', 'public'),  # 可选，缺省公开（管理员后台可收紧）
                    'author': config.get('author', '佚名'),  # 可选，缺省佚名
                    'description': config.get('description', '暂无描述'),  # 可选，缺省暂无描述
                    'version': config['version'],  # 必填
                    'category': config['category'],  # 必填
                    'require_framework_version': config.get('require_framework_version', ''),  # 可选
                    'enabled': True,
                    'type': 'frontend',
                    'install_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'source': temp_filename,
                    'history': [{'version': str(config['version']), 'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'source': temp_filename}]
                })

                # 写入配置文件
                with open(global_var.FRONTEND_CONFIG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(global_var.frontend_tools, f, ensure_ascii=False, indent=2)

                logger.info(f"已上传前端工具: {tool_name} v{config['version']}", extra={'plugin': 'system'})
                log_audit('前端工具安装', tool_name, 'ok', f"v{config['version']} 来源 {temp_filename}")
                return jsonify({"code": 200, "message": "工具上传成功", "data": config})

        except zipfile.BadZipFile:
            return jsonify({"code": 400, "message": "无效的zip文件"}), 400
        finally:
            # 删除临时文件（清理失败不阻塞接口返回）
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as e:
                    logger.warning(f"上传临时文件清理失败: {temp_path} - {e}")

    @app.route('/api/admin/frontend/<tool_name>/update', methods=['POST'])
    @admin_api
    def update_frontend_tool(tool_name):
        """更新前端工具"""
        # 检查工具是否存在
        tool_index = next((i for i, t in enumerate(global_var.frontend_tools) if t['name'] == tool_name), None)
        if tool_index is None:
            return jsonify({"code": 404, "message": "工具不存在"}), 404

        current_tool = global_var.frontend_tools[tool_index]

        if 'file' not in request.files:
            return jsonify({"code": 400, "message": "未上传更新包"}), 400

        file = request.files['file']
        if not file.filename.endswith('.zip'):
            return jsonify({"code": 400, "message": "仅支持zip格式包"}), 400

        # 包大小上限校验（超限返回 413）
        oversize = check_upload_size(file, global_var.PACKAGE_MAX_UPLOAD_SIZE)
        if oversize:
            return jsonify({
                "code": 413,
                "message": f"工具包大小超过限制 {global_var.PACKAGE_MAX_UPLOAD_SIZE // (1024 * 1024)}MB（实际约 {oversize // (1024 * 1024)}MB）"
            }), 413

        temp_filename = secure_filename_cn(file.filename)
        temp_path = os.path.join(global_var.UPLOAD_TEMP_DIR, temp_filename)
        file.save(temp_path)

        try:
            # 完整性校验（P2-4 方案C）
            vres = verify_package(temp_path, 'frontend')
            if not vres['ok']:
                return jsonify({"code": 400, "message": vres['message']}), 400
            if vres.get('warn_only'):
                logger.warning(vres['message'], extra={'plugin': 'system'})
            with zipfile.ZipFile(temp_path, 'r') as zf:
                if 'config.json' not in zf.namelist():
                    return jsonify({"code": 400, "message": "更新包缺少config.json配置文件"}), 400

                with zf.open('config.json', 'r') as f:
                    config = json.load(f)

                # 校验必填字段
                required_fields = ['name', 'version', 'category']
                for field in required_fields:
                    if field not in config:
                        return jsonify({"code": 400, "message": f"config.json缺少必填字段: {field}"}), 400

                if config.get('name') != tool_name:
                    return jsonify({"code": 400, "message": "更新包名称与原工具不匹配"}), 400

                # 版本号校验：新版本必须大于当前版本
                if config['version'] <= current_tool['version']:
                    return jsonify({
                        "code": 400,
                        "message": f"更新包版本必须高于当前版本，当前版本: {current_tool['version']}，更新包版本: {config['version']}"
                    }), 400

                # 框架版本校验：点分版本比较（修复字符串比较缺陷）
                if 'require_framework_version' in config:
                    if compare_versions(config['require_framework_version'], global_var.FRAMEWORK_VERSION) > 0:
                        return jsonify({
                            "code": 400,
                            "message": f"工具要求框架最低版本为 {config['require_framework_version']}，当前版本为 {global_var.FRAMEWORK_VERSION}"
                        }), 400

                html_file = f"{tool_name}.html"
                if html_file not in zf.namelist():
                    return jsonify({"code": 400, "message": f"更新包缺少入口文件: {html_file}"}), 400

                # 覆盖 html + 静态资源（先清理旧 static 目录，避免残留旧版本文件）
                safe_extract_frontend(zf, tool_name, global_var.FRONTEND_TEMPLATE_DIR, clean_static=True)

                # 更新配置（适配新字段）
                global_var.frontend_tools[tool_index].update({
                    'title': config.get('title', current_tool['title']),
                    'author': config.get('author', current_tool['author']),
                    'description': config.get('description', current_tool['description']),
                    'version': config['version'],
                    'category': config['category'],
                    'require_framework_version': config.get('require_framework_version', current_tool.get('require_framework_version', '')),
                    'permission': config.get('permission', current_tool.get('permission', 'public'))
                })
                # 溯源：保留 install_time，追加版本历史
                _now = time.strftime('%Y-%m-%d %H:%M:%S')
                _hist = list(current_tool.get('history', []))
                _hist.append({'version': str(config['version']), 'time': _now, 'source': temp_filename})
                global_var.frontend_tools[tool_index]['history'] = _hist
                global_var.frontend_tools[tool_index]['install_time'] = current_tool.get('install_time', _now)
                global_var.frontend_tools[tool_index]['source'] = temp_filename

                with open(global_var.FRONTEND_CONFIG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(global_var.frontend_tools, f, ensure_ascii=False, indent=2)

                logger.info(f"已更新前端工具: {tool_name} 从v{current_tool['version']}到v{config['version']}", extra={'plugin': 'system'})
                log_audit('前端工具更新', tool_name, 'ok', f"v{current_tool['version']}→v{config['version']} 来源 {temp_filename}")
                return jsonify({"code": 200, "message": "工具更新成功"})

        finally:
            # 删除临时文件（清理失败不阻塞接口返回）
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as e:
                    logger.warning(f"更新临时文件清理失败: {temp_path} - {e}")

    @app.route('/api/admin/frontend/<tool_name>/uninstall', methods=['POST'])
    @admin_api
    def uninstall_frontend_tool(tool_name):
        """卸载前端工具"""
        tool_index = next((i for i, t in enumerate(global_var.frontend_tools) if t['name'] == tool_name), None)
        if tool_index is None:
            return jsonify({"code": 404, "message": "工具不存在"}), 404

        # 删除资源文件（入口 html + 静态资源目录）
        cleanup_frontend_resources(tool_name)

        # 删除统计数据
        stats_key = f"frontend:{tool_name}"
        if stats_key in global_var.frontend_access_stats:
            del global_var.frontend_access_stats[stats_key]
            save_stats()

        # 移除配置
        del global_var.frontend_tools[tool_index]
        with open(global_var.FRONTEND_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(global_var.frontend_tools, f, ensure_ascii=False, indent=2)

        logger.info(f"已卸载前端工具: {tool_name}", extra={'plugin': 'system'})
        log_audit('前端工具卸载', tool_name, 'ok')
        return jsonify({"code": 200, "message": "工具卸载成功"})

    # 新增前端工具状态管理
    @app.route('/api/admin/frontend/<tool_name>/enable', methods=['POST'])
    @admin_api
    def enable_frontend_tool(tool_name):
        """启用前端工具"""
        # 直接读取并修改配置文件原始数据
        config_file = global_var.FRONTEND_CONFIG_FILE
        if not os.path.exists(config_file):
            return jsonify({"code": 404, "message": "前端工具配置文件不存在"}), 404

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        except Exception as e:
            logger.error(f"读取配置文件失败: {str(e)}", extra={'plugin': 'system'})
            return jsonify({"code": 500, "message": "配置文件读取失败"}), 500

        # 查找并修改对应工具的enabled状态
        tool_found = False
        for tool in config_data:
            if isinstance(tool, dict) and tool.get('name') == tool_name:
                tool['enabled'] = True
                tool_found = True
                break

        if not tool_found:
            return jsonify({"code": 404, "message": "前端工具不存在"}), 404

        # 写入修改后的完整配置到文件
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)

        # 重新加载前端工具到内存
        load_frontend_tools()

        logger.info(f"已启用前端工具: {tool_name}", extra={'plugin': 'system'})
        log_audit('前端工具启用', tool_name, 'ok')
        return jsonify({"code": 200, "message": f"前端工具 {tool_name} 已启用"})

    @app.route('/api/admin/frontend/<tool_name>/disable', methods=['POST'])
    @admin_api
    def disable_frontend_tool(tool_name):
        """禁用前端工具"""
        # 直接读取并修改配置文件原始数据
        config_file = global_var.FRONTEND_CONFIG_FILE
        if not os.path.exists(config_file):
            return jsonify({"code": 404, "message": "前端工具配置文件不存在"}), 404

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        except Exception as e:
            logger.error(f"读取配置文件失败: {str(e)}", extra={'plugin': 'system'})
            return jsonify({"code": 500, "message": "配置文件读取失败"}), 500

        # 查找并修改对应工具的enabled状态
        tool_found = False
        for tool in config_data:
            if isinstance(tool, dict) and tool.get('name') == tool_name:
                tool['enabled'] = False
                tool_found = True
                break

        if not tool_found:
            return jsonify({"code": 404, "message": "前端工具不存在"}), 404

        # 写入修改后的完整配置到文件
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)

        # 重新加载前端工具到内存
        load_frontend_tools()

        logger.info(f"已禁用前端工具: {tool_name}", extra={'plugin': 'system'})
        log_audit('前端工具禁用', tool_name, 'ok')
        return jsonify({"code": 200, "message": f"前端工具 {tool_name} 已禁用"})

    @app.route('/api/admin/frontend/<tool_name>/permission', methods=['POST'])
    @admin_api
    def change_frontend_permission(tool_name):
        """修改前端工具访问权限（public/user/admin）"""
        data = request.get_json(silent=True) or {}
        new_permission = str(data.get('permission', '')).strip().lower()
        if new_permission not in ('public', 'user', 'admin'):
            return jsonify({"code": 400, "message": "权限值无效，仅支持 public/user/admin"}), 400

        config_file = global_var.FRONTEND_CONFIG_FILE
        if not os.path.exists(config_file):
            return jsonify({"code": 404, "message": "前端工具配置文件不存在"}), 404

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        except Exception as e:
            logger.error(f"读取配置文件失败: {str(e)}", extra={'plugin': 'system'})
            return jsonify({"code": 500, "message": "配置文件读取失败"}), 500

        tool_found = False
        for tool in config_data:
            if isinstance(tool, dict) and tool.get('name') == tool_name:
                tool['permission'] = new_permission
                tool_found = True
                break

        if not tool_found:
            return jsonify({"code": 404, "message": "前端工具不存在"}), 404

        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)

        # 重新加载前端工具到内存
        load_frontend_tools()

        logger.info(f"已修改前端工具权限: {tool_name} -> {new_permission}", extra={'plugin': 'system'})
        log_audit('前端工具权限修改', tool_name, 'ok', f"permission={new_permission}")
        return jsonify({"code": 200, "message": f"前端工具 {tool_name} 权限已更新为 {new_permission}"})
