# -*- coding: utf-8 -*-
"""
插件加载器：依赖校验、定时任务注册、插件发现与按拓扑序加载

- load_plugins() 无参：通过 global_var 引用共享状态（plugins/plugin_categories/
  loaded_module_names/scheduler/plugin_status/app），保持同一对象，避免与 app.py
  显式导入的引用脱钩。
- 注意：plugin_categories 用 clear() 而非重新赋值，否则 app.py 的显式导入引用会失效。
"""
import importlib
import importlib.metadata
import logging
import os
import sys
import traceback

import global_var
from core.logging_setup import PluginLogAdapter
from core.permission import wrap_page_func, wrap_view_func
from core.plugin_cache import (is_cache_valid, load_plugin_cache, save_plugin_cache, scan_plugin_metadata)
from core.capabilities import (clear_capabilities, load_capabilities_from_desc,
                              register_capabilities)
from core.plugin_pack import check_framework_version
from core.plugin_status import load_plugin_status
from core.stats import save_stats
from core.utils import parse_path_pattern

logger = logging.getLogger('flask.app')


def check_dependencies(plugin_instance, available_plugins: set) -> list[str]:
    """
    校验插件依赖
    :param plugin_instance: 待校验插件实例
    :param available_plugins: 当前系统中存在的所有插件名集合
    :return: 缺失的依赖列表（插件名或包名）
    """
    missing = []
    for dep in plugin_instance.dependencies:
        # 优先判断是否是插件依赖
        if dep in available_plugins:
            continue
        # 再判断是否是第三方Python包
        try:
            importlib.metadata.distribution(dep)
        except importlib.metadata.PackageNotFoundError:
            missing.append(dep)
    return missing


def register_scheduled_tasks(plugin_instance):
    for task_config in plugin_instance.scheduled_tasks:
        task_func = task_config.pop('func')
        task_id = f"{plugin_instance.name}_{task_func.__name__}"
        if global_var.scheduler.get_job(task_id):
            global_var.scheduler.remove_job(task_id)
        global_var.scheduler.add_job(
            func=task_func,
            id=task_id,
            **task_config
        )
        logger.info(f"已注册定时任务: {task_id}", extra={'plugin': plugin_instance.name})


def load_plugins():
    plugin_dir = os.path.join(global_var.BASE_DIR, 'plugins')
    global_temp_root = os.path.join(plugin_dir, 'temp')
    os.makedirs(global_temp_root, exist_ok=True)

    # 清理旧缓存（模块缓存）
    base_module_name = 'plugins.base_plugin'
    if base_module_name in sys.modules:
        del sys.modules[base_module_name]
        logger.info("已清理旧版插件基类缓存", extra={'plugin': 'system'})

    for module_name in list(sys.modules.keys()):
        if module_name.startswith('plugins.') and module_name in global_var.loaded_module_names:
            del sys.modules[module_name]

    old_plugin_names = list(global_var.plugins.keys())
    # 保持同一对象：用 clear() 而非重新赋值
    global_var.plugin_categories.clear()
    global_var.loaded_module_names.clear()

    for job in global_var.scheduler.get_jobs():
        if job.id.startswith(tuple([name + "_" for name in old_plugin_names])):
            global_var.scheduler.remove_job(job.id)

    # ==================== 加载插件状态 ====================
    _, current_status_hash = load_plugin_status()

    # ==================== 缓存加速的插件发现 ====================
    discovered_plugins = []

    # 尝试从缓存加载
    cache = load_plugin_cache()
    if cache and is_cache_valid(cache, plugin_dir, current_status_hash):
        discovered_plugins = cache['discovered_plugins']
        logger.info(f"使用缓存发现结果，跳过扫描（{len(discovered_plugins)} 个插件）", extra={'plugin': 'system'})
    else:
        # 缓存无效，重新扫描
        logger.info("开始扫描插件元信息...", extra={'plugin': 'system'})
        discovered_plugins = scan_plugin_metadata(plugin_dir)
        save_plugin_cache(discovered_plugins, plugin_dir)

    # 构建插件元信息字典
    plugin_meta = {}
    for info in discovered_plugins:
        module_name = f'plugins.{info["file"][:-3]}'
        try:
            module = importlib.import_module(module_name)
            global_var.loaded_module_names.add(module_name)
            plugin_class = getattr(module, info['class_name'])
            plugin_meta[info['name']] = {
                "class": plugin_class,
                "dependencies": info['dependencies'],
                "category": info['category'],
                "description": info['description'],
                "version": info['version'],
                "require_framework_version": info.get('require_framework_version', ''),
            }
        except Exception as e:
            logger.error(f"导入插件 {info['name']} 模块失败: {str(e)}", extra={'plugin': 'system'})

    available_plugin_names = set(plugin_meta.keys())
    logger.info(f"发现 {len(available_plugin_names)} 个插件: {', '.join(available_plugin_names)}", extra={'plugin': 'system'})

    # ==================== 拓扑排序 ====================
    sorted_plugin_names = []
    visited = set()
    temp_visited = set()

    def dfs(plugin_name):
        if plugin_name in temp_visited:
            raise RuntimeError(f"检测到插件循环依赖: {plugin_name}")
        if plugin_name in visited:
            return
        if plugin_name not in plugin_meta:
            logger.debug(f"可选依赖插件 {plugin_name} 不存在，跳过", extra={'plugin': 'system'})
            return

        temp_visited.add(plugin_name)
        for dep in plugin_meta[plugin_name]["dependencies"]:
            dfs(dep)
        temp_visited.remove(plugin_name)
        visited.add(plugin_name)
        sorted_plugin_names.append(plugin_name)

    for plugin_name in plugin_meta.keys():
        if plugin_name not in visited:
            dfs(plugin_name)

    logger.info(f"插件加载顺序: {', '.join(sorted_plugin_names)}", extra={'plugin': 'system'})

    # 能力注册表清空（v4.3.2）：重载时按现存插件重建，
    # 作为阶段三（4.4.0）运行时审计钩子的授权基准
    clear_capabilities()

    # ==================== 按顺序加载插件 ====================
    loaded_plugins = []
    for plugin_name in sorted_plugin_names:
        try:
            plugin_class = plugin_meta[plugin_name]["class"]
            plugin_instance = plugin_class()

            # 最低框架版本校验（可选字段，声明后须满足；防止手工放置插件绕过上传校验）
            req_ver = plugin_meta[plugin_name].get('require_framework_version')
            if req_ver:
                ok, msg = check_framework_version(req_ver)
                if not ok:
                    logger.warning(
                        f"插件 {plugin_name} 不满足框架版本要求，跳过加载: {msg}",
                        extra={'plugin': 'system'},
                    )
                    continue

            # 注册能力声明（v4.3.2）：从插件描述文件读取 capabilities 并注册
            caps = load_capabilities_from_desc(
                os.path.join(global_var.BASE_DIR, 'plugins', f'{plugin_name}.json'))
            register_capabilities(plugin_instance.name, caps)

            # 注入logger
            plugin_instance.logger = PluginLogAdapter(logger, {'plugin': plugin_instance.name})

            # 注册静态资源
            plugin_instance.register_static_routes(global_var.app)

            # 处理临时目录
            plugin_global_temp_root = os.path.join(global_var.BASE_DIR, 'plugins', 'temp')
            if plugin_instance.get_temp_dir() == "__LEGACY_DEFAULT__":
                plugin_instance.set_temp_dir(plugin_global_temp_root)
                logger.info(f"插件 {plugin_instance.name} 使用旧版全局临时目录（兼容模式）", extra={'plugin': 'system'})
            elif plugin_instance.get_temp_dir() == "__NEW_PLUGIN_DEFAULT__":
                plugin专属目录 = os.path.join(plugin_global_temp_root, plugin_instance.name)
                plugin_instance.set_temp_dir(plugin专属目录)
                logger.info(f"插件 {plugin_instance.name} 使用新版专属隔离目录: {plugin专属目录}", extra={'plugin': 'system'})
            else:
                custom_dir = plugin_instance.get_temp_dir()
                os.makedirs(custom_dir, exist_ok=True)
                logger.info(f"插件 {plugin_instance.name} 使用自定义临时目录: {custom_dir}", extra={'plugin': 'system'})

            # ==================== 处理启用状态 ====================
            enabled = global_var.plugin_status.get(plugin_instance.name, {}).get('enabled', True)
            plugin_instance.enabled = enabled
            if not enabled:
                logger.info(f"插件 {plugin_instance.name} 已禁用，跳过加载", extra={'plugin': 'system'})
                # 已禁用的插件不注册路由和分类，但保留在 plugins 字典中
                global_var.plugins[plugin_instance.name] = plugin_instance
                continue

            # 校验依赖
            missing_deps = check_dependencies(plugin_instance, available_plugin_names)
            if missing_deps:
                logger.warning(f"插件 {plugin_instance.name} 缺少依赖: {', '.join(missing_deps)}，跳过加载", extra={'plugin': 'system'})
                continue

            # 注册路由
            plugin_instance._wrapped_routes = {}
            plugin_instance._wrapped_pages = {}  # 页面路由（大插件多模板）：path -> {'view_func','template'}
            for route in plugin_instance.routes:
                wrapped_view = wrap_view_func(route['view_func'], plugin_instance.name, route)
                path = route['path']
                methods = tuple(route.get('methods', ['GET']))
                # 页面路由：声明 page=True 时注册为插件子页面 /plugin/<name>/<subpath>，
                # view_func 返回渲染上下文 dict（分发器渲染到插件模板）或 Response（原样返回）
                if route.get('page'):
                    page_tpl = route.get('template') or (path.strip('/').rsplit('/', 1)[-1] + '.html')
                    plugin_instance._wrapped_pages[path] = {
                        'view_func': wrapped_view,
                        'template': page_tpl,
                    }
                    continue  # 页面路由不进 API 分发
                if path not in plugin_instance._wrapped_routes:
                    plugin_instance._wrapped_routes[path] = {}
                plugin_instance._wrapped_routes[path][methods] = wrapped_view

                # ==================== 新增：预计算路径参数的正则模式 ====================
                # 如果路径包含参数（如 <pack_id>），预计算正则表达式
                if '<' in path:
                    pattern, param_names = parse_path_pattern(path)
                    if not hasattr(plugin_instance, '_wrapped_routes_patterns'):
                        plugin_instance._wrapped_routes_patterns = []
                    plugin_instance._wrapped_routes_patterns.append({
                        'pattern': pattern,
                        'param_names': param_names,
                        'path': path,
                        'methods': methods,
                        'view_func': wrapped_view
                    })

            plugin_instance._wrapped_page = wrap_page_func(plugin_instance.render_plugin_page, plugin_instance.name)

            # 注册到全局注册表
            global_var.plugins[plugin_instance.name] = plugin_instance

            # 执行加载钩子
            plugin_instance.on_load()

            # 注册定时任务
            register_scheduled_tasks(plugin_instance)

            # 分类统计
            category = plugin_instance.category
            if category not in global_var.plugin_categories:
                global_var.plugin_categories[category] = []
            global_var.plugin_categories[category].append({
                'name': plugin_instance.name,
                'description': plugin_instance.description,
                'version': plugin_instance.version,
                'page_url': f'/plugin/{plugin_instance.name}',
                'enabled': True
            })

            loaded_plugins.append(f"{plugin_instance.name} v{plugin_instance.version}")
            logger.info(f"已加载插件: {plugin_instance.name} - {plugin_instance.description}", extra={'plugin': 'system'})

        except Exception as e:
            logger.error(f"加载插件 {plugin_name} 失败: {str(e)}\n{traceback.format_exc()}", extra={'plugin': 'system'})
            global_var.plugins.pop(plugin_name, None)

    # ==================== on_ready 就绪钩子（v4.2.2）：所有插件加载完成后统一调用 ====================
    # 此时 global_var.plugins 已包含全部可用插件，跨插件依赖检查结果准确；
    # 严格模式（PLUGIN_STRICT_MODE）下插件可在此延后执行依赖确认（on_load 仅记录 warning）。
    for _pname in list(global_var.plugins.keys()):
        _pinst = global_var.plugins[_pname]
        if hasattr(_pinst, 'on_ready'):
            try:
                _pinst.on_ready()
                logger.debug(f"插件 {_pname} on_ready 就绪回调完成", extra={'plugin': 'system'})
            except Exception as _e:
                logger.error(f"插件 {_pname} on_ready 回调失败: {_e}\n{traceback.format_exc()}", extra={'plugin': 'system'})

    # 注册系统定时任务
    if not global_var.scheduler.get_job('system_stats_save'):
        global_var.scheduler.add_job(
            id='system_stats_save',
            func=save_stats,
            trigger='interval',
            minutes=5,
            replace_existing=True
        )
        logger.info("已注册系统统计数据定时保存任务", extra={'plugin': 'system'})

    # ==================== 构建插件目录（内存注册表，供首页/管理页直接读取，避免每次请求扫描磁盘） ====================
    global_var.plugin_catalog.clear()
    for info in discovered_plugins:
        _name = info['name']
        _meta = {
            'name': _name,
            'title': info.get('title', _name),
            'author': info.get('author', '佚名'),
            'description': info.get('description', '暂无描述'),
            'version': info.get('version', '0.0.0'),
            'category': info.get('category', '其他工具'),
            'permission': info.get('permission', 'user'),
            'dependencies': info.get('dependencies', []),
            'require_framework_version': info.get('require_framework_version', ''),
            'type': 'backend',
            'builtin': _name in global_var.BUILTIN_PLUGINS,
            'enabled': global_var.plugin_status.get(_name, {}).get('enabled', True),
            'loaded': _name in global_var.plugins,
            'api_calls': sum(v for k, v in global_var.call_stats.items() if k.startswith(f"{_name}:")),
            'page_url': f'/plugin/{_name}',
        }
        # 已加载插件用实例属性覆盖（更准确）
        _inst = global_var.plugins.get(_name)
        if _inst is not None:
            _meta['title'] = getattr(_inst, 'title', _meta['title'])
            _meta['author'] = getattr(_inst, 'author', _meta['author'])
            _meta['permission'] = getattr(_inst, 'permission', _meta['permission'])
        global_var.plugin_catalog.append(_meta)

    logger.info(f"加载完成，共加载 {len(loaded_plugins)} 个插件", extra={'plugin': 'system'})
    logger.info(f"最终注册表内容: {list(global_var.plugins.keys())}", extra={'plugin': 'system'})
