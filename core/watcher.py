# -*- coding: utf-8 -*-
"""
文件监听器：插件/前端工具变更检测，触发增量重载

- 所有路径通过 global_var 引用（BASE_DIR/FRONTEND_CONFIG_FILE/FRONTEND_TEMPLATE_DIR 等）。
- 日志使用 logging.getLogger('flask.app')。
"""
import importlib
import json
import logging
import os
import sys
import time
import traceback

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import global_var
from core.plugin_pack import META_FIELDS
from core.frontend_tools import load_frontend_tools
from core.plugin_cache import (compute_directory_fingerprint, compute_file_fingerprint, load_plugin_cache)
from core.plugin_loader import load_plugins

logger = logging.getLogger('flask.app')


class PluginFileHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_reload = 0

    def on_modified(self, event):
        if event.is_directory:
            return
        filepath = event.src_path
        current_time = time.time()

        # 原有插件变更检测逻辑
        plugin_changed = (
            (filepath.endswith('.py') and 'plugins' in filepath and 'base_plugin.py' not in filepath) or
            (filepath.endswith('.json') and 'plugins/configs' in filepath)
        )

        # 前端工具变更检测逻辑
        frontend_tool_changed = (
            (filepath.endswith('.json') and 'frontend_tools.json' in filepath) or
            (filepath.endswith('.html') and 'templates/frontend_tools' in filepath)
        )

        if plugin_changed or frontend_tool_changed:
            if current_time - self.last_reload < 2:  # 2秒防抖
                return
            self.last_reload = current_time

            if plugin_changed:
                logger.info(f"检测到插件变更: {filepath}，正在增量重载...", extra={'plugin': 'system'})
                try:
                    # ==================== 增量更新缓存 ====================
                    incremental_update_cache(filepath)
                    # ==================== 重新加载插件 ====================
                    load_plugins()
                    logger.info("插件增量重载完成！", extra={'plugin': 'system'})
                except Exception as e:
                    logger.error(f"插件增量重载失败: {str(e)}\n{traceback.format_exc()}", extra={'plugin': 'system'})

            if frontend_tool_changed:
                logger.info("检测到前端工具变更，正在重载...", extra={'plugin': 'system'})
                try:
                    load_frontend_tools()
                    logger.info("前端工具重载完成！", extra={'plugin': 'system'})
                except Exception as e:
                    logger.error(f"前端工具重载失败: {str(e)}\n{traceback.format_exc()}", extra={'plugin': 'system'})


def incremental_update_cache(changed_filepath: str):
    """
    增量更新缓存：只更新变更文件对应的缓存条目
    :param changed_filepath: 变更文件的完整路径
    """
    plugin_dir = os.path.join(global_var.BASE_DIR, 'plugins')

    # 读取现有缓存
    cache = load_plugin_cache()
    if not cache:
        logger.info("无现有缓存，将由 load_plugins 全量重建", extra={'plugin': 'system'})
        return

    # 判断变更类型
    filename = os.path.basename(changed_filepath)

    # ====== 情况1：配置文件变更（configs/xxx.json） ======
    if 'configs' in changed_filepath and filename.endswith('.json'):
        logger.info("配置文件变更，仅重载插件即可（元信息不变）", extra={'plugin': 'system'})
        # 配置文件变更不影响插件元信息，缓存不需要更新
        # 但目录指纹要更新（因为配置文件也在插件目录下）
        cache['dir_fingerprint'] = compute_directory_fingerprint(plugin_dir)
        cache['timestamp'] = time.time()
        save_cache_internal(cache)
        return

    # ====== 情况2：插件 .py 文件变更 ======
    if filename.endswith('.py') and filename not in ['__init__.py', 'base_plugin.py']:
        plugin_name = filename[:-3]  # 去掉 .py

        # 检查文件是否存在（可能被删除）
        if not os.path.exists(changed_filepath):
            # ====== 插件被删除 ======
            logger.info(f"插件文件 {filename} 已被删除，从缓存中移除", extra={'plugin': 'system'})
            cache['discovered_plugins'] = [
                info for info in cache['discovered_plugins']
                if info['file'] != filename
            ]
            cache['fingerprints'].pop(plugin_name, None)
        else:
            # ====== 插件被新增或修改 ======
            logger.info(f"插件文件 {filename} 已变更，更新缓存", extra={'plugin': 'system'})

            # 重新扫描该文件
            module_name = f'plugins.{plugin_name}'
            try:
                # 清理模块缓存确保重新导入
                if module_name in sys.modules:
                    del sys.modules[module_name]

                module = importlib.import_module(module_name)

                new_plugin_info = None
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type):
                        if any(base.__name__ == 'BasePlugin' for base in attr.__mro__) and attr.__name__ != 'BasePlugin':
                            temp_inst = attr()
                            new_plugin_info = {
                                'name': temp_inst.name,
                                'file': filename,
                                'class_name': attr.__name__,
                                'dependencies': temp_inst.dependencies,
                                'category': getattr(temp_inst, 'category', 'uncategorized'),
                                'description': getattr(temp_inst, 'description', ''),
                                'version': getattr(temp_inst, 'version', '0.0.0'),
                                'title': getattr(temp_inst, 'title', temp_inst.name),
                                'author': getattr(temp_inst, 'author', '佚名'),
                                'permission': getattr(temp_inst, 'permission', 'user'),
                                'require_framework_version': getattr(temp_inst, 'require_framework_version', '')
                            }
                            break

                if new_plugin_info:
                    # 插件包描述文件为权威：整体覆盖（与 scan_plugin_metadata 保持一致）
                    meta_file = os.path.join(global_var.BASE_DIR, 'plugins', f"{new_plugin_info['name']}.json")
                    if os.path.isfile(meta_file):
                        try:
                            with open(meta_file, 'r', encoding='utf-8') as _mf:
                                _meta = json.load(_mf)
                            if isinstance(_meta, dict):
                                if _meta.get('name') and _meta['name'] != new_plugin_info['name']:
                                    logger.error(
                                        f"插件描述文件 name 与插件类 name 不一致，跳过更新缓存: "
                                        f"{_meta.get('name')} vs {new_plugin_info['name']}",
                                        extra={'plugin': 'system'})
                                    return
                                for _k in META_FIELDS:
                                    if _k in _meta:
                                        new_plugin_info[_k] = _meta[_k]
                        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
                            logger.warning(f"读取插件描述文件失败，忽略: {meta_file}", extra={'plugin': 'system'})
                    # 更新缓存中的条目
                    existing = [i for i in cache['discovered_plugins'] if i['file'] == filename]
                    if existing:
                        # 更新已有条目
                        for i, info in enumerate(cache['discovered_plugins']):
                            if info['file'] == filename:
                                cache['discovered_plugins'][i] = new_plugin_info
                                break
                    else:
                        # 新增条目
                        cache['discovered_plugins'].append(new_plugin_info)

                    # 更新文件指纹
                    cache['fingerprints'][new_plugin_info['name']] = compute_file_fingerprint(changed_filepath)

                    # 如果插件名变了，清理旧指纹
                    if existing and existing[0]['name'] != new_plugin_info['name']:
                        cache['fingerprints'].pop(existing[0]['name'], None)

                else:
                    logger.warning(f"文件 {filename} 中未找到有效的插件类", extra={'plugin': 'system'})

            except Exception as e:
                logger.error(f"增量扫描插件 {filename} 失败: {str(e)}", extra={'plugin': 'system'})
                # 失败时不清除缓存，但标记该插件可能有问题
                return

        # 更新目录指纹
        cache['dir_fingerprint'] = compute_directory_fingerprint(plugin_dir)
        cache['timestamp'] = time.time()

        # 写回缓存
        save_cache_internal(cache)


def save_cache_internal(cache: dict):
    """
    将缓存数据写回磁盘（内部方法，不重新计算状态哈希）
    """
    os.makedirs(global_var.PLUGIN_CACHE_DIR, exist_ok=True)

    # 确保版本号正确
    cache['version'] = global_var.CACHE_VERSION

    temp_file = global_var.PLUGIN_CACHE_FILE + '.tmp'
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
        os.replace(temp_file, global_var.PLUGIN_CACHE_FILE)
        logger.info("缓存已增量更新", extra={'plugin': 'system'})
    except Exception as e:
        logger.error(f"缓存增量更新失败: {e}", extra={'plugin': 'system'})
        if os.path.exists(temp_file):
            os.remove(temp_file)


def start_file_watcher():
    event_handler = PluginFileHandler()
    observer = Observer()

    # 原有插件目录监听
    plugin_dir = os.path.join(global_var.BASE_DIR, 'plugins')
    observer.schedule(event_handler, plugin_dir, recursive=True)

    # 新增前端工具配置文件监听
    frontend_config_path = global_var.FRONTEND_CONFIG_FILE
    if os.path.exists(frontend_config_path):
        observer.schedule(event_handler, os.path.dirname(frontend_config_path), recursive=False)

    # 新增前端工具模板目录监听
    frontend_tpl_dir = global_var.FRONTEND_TEMPLATE_DIR
    if os.path.exists(frontend_tpl_dir):
        observer.schedule(event_handler, frontend_tpl_dir, recursive=True)

    observer.start()
    return observer
