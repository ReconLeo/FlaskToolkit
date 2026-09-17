# -*- coding: utf-8 -*-
"""
插件发现缓存：目录指纹 + 逐文件指纹 + 状态快照哈希，加速插件扫描

- 缓存文件路径/版本号等常量一律通过 global_var 引用。
- 日志使用 logging.getLogger('flask.app')。
"""
import hashlib
import importlib
import json
import logging
import os
import time

import global_var
from core.plugin_pack import META_FIELDS, plugin_meta_file, plugin_main_file
from core.plugin_status import load_plugin_status

logger = logging.getLogger('flask.app')


def compute_file_fingerprint(filepath: str) -> str:
    """
    计算单个文件的复合指纹（SHA-1 + MD5）
    使用双哈希降低碰撞概率，同时兼顾速度（SHA-1快，MD5更广支持）
    """
    sha1 = hashlib.sha1()
    md5 = hashlib.md5()

    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            sha1.update(chunk)
            md5.update(chunk)

    return f"{sha1.hexdigest()}+{md5.hexdigest()}"


def _iter_plugin_files(plugin_dir: str):
    """产出插件相关文件的相对路径（正斜杠）：扁平主文件 + 目录化插件目录内 .py/.json。

    覆盖 v4.21 目录化布局：每个插件一个自包含目录 plugins/<name>/，其内文件均算插件文件
    （否则目录化插件变更不反映在目录指纹，缓存失效判断失效）。
    """
    _skip_top = ('__init__.py', 'base_plugin.py', 'status.json',
                 'configs', 'temp', 'data', '__pycache__')
    for fn in sorted(os.listdir(plugin_dir)):
        full = os.path.join(plugin_dir, fn)
        if fn in _skip_top:
            continue
        if os.path.isfile(full):
            if (fn.endswith('.py') or fn.endswith('.json')):
                yield fn
        elif os.path.isdir(full):
            for root, dirs, files in os.walk(full):
                dirs[:] = [d for d in dirs if d not in ('__pycache__',)]
                for f in files:
                    if f.endswith(('.py', '.json')):
                        rel = os.path.relpath(os.path.join(root, f), plugin_dir)
                        yield rel.replace(os.sep, '/')

def compute_directory_fingerprint(plugin_dir: str) -> str:
    """
    计算插件目录的整体指纹（含目录化插件子目录）。
    包含：插件相关文件的相对路径 + 对应指纹，用于快速判断新增/删除/修改。
    """
    hasher = hashlib.sha256()
    rel_files = sorted(_iter_plugin_files(plugin_dir))
    plugin_files = []
    for rel in rel_files:
        filepath = os.path.join(plugin_dir, rel.replace('/', os.sep))
        fingerprint = compute_file_fingerprint(filepath)
        plugin_files.append(f"{rel}:{fingerprint}")
    hasher.update(",".join(rel_files).encode('utf-8'))
    hasher.update("|".join(plugin_files).encode('utf-8'))
    return hasher.hexdigest()


def load_plugin_cache() -> dict | None:
    """
    加载缓存文件
    返回 None 表示缓存不存在或无效
    """
    if not os.path.exists(global_var.PLUGIN_CACHE_FILE):
        return None

    try:
        with open(global_var.PLUGIN_CACHE_FILE, 'r', encoding='utf-8') as f:
            cache = json.load(f)

        # 版本校验
        if cache.get('version') != global_var.CACHE_VERSION:
            logger.info("插件缓存版本不匹配，将重新扫描", extra={'plugin': 'system'})
            return None

        return cache
    except (json.JSONDecodeError, KeyError, IOError) as e:
        logger.warning(f"插件缓存读取失败: {e}，将重新扫描", extra={'plugin': 'system'})
        return None


def save_plugin_cache(discovered_plugins: list[dict], plugin_dir: str):
    """
    保存插件发现结果到缓存（含状态快照）
    """
    os.makedirs(global_var.PLUGIN_CACHE_DIR, exist_ok=True)

    # 计算每个文件的指纹
    fingerprints = {}
    for info in discovered_plugins:
        filepath = os.path.join(plugin_dir, info['file'])
        if os.path.exists(filepath):
            fingerprints[info['name']] = compute_file_fingerprint(filepath)

    # 获取当前状态并计算哈希
    _, status_hash = load_plugin_status()

    cache_data = {
        'version': global_var.CACHE_VERSION,
        'fingerprints': fingerprints,
        'dir_fingerprint': compute_directory_fingerprint(plugin_dir),
        'discovered_plugins': discovered_plugins,
        'status_snapshot': global_var.plugin_status,       # 保存状态快照
        'status_hash': status_hash,                        # 保存状态哈希
        'timestamp': time.time()
    }

    # 原子写入
    temp_file = global_var.PLUGIN_CACHE_FILE + '.tmp'
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
        os.replace(temp_file, global_var.PLUGIN_CACHE_FILE)
        logger.info(f"插件缓存已保存（含状态快照），共 {len(discovered_plugins)} 个插件", extra={'plugin': 'system'})
    except Exception as e:
        logger.error(f"插件缓存保存失败: {e}", extra={'plugin': 'system'})
        if os.path.exists(temp_file):
            os.remove(temp_file)


def is_cache_valid(cache: dict, plugin_dir: str, current_status_hash: str) -> bool:
    """
    验证缓存是否仍然有效
    :param cache: 缓存数据
    :param plugin_dir: 插件目录
    :param current_status_hash: 当前插件状态哈希
    """
    # 1. 目录指纹校验
    current_dir_fp = compute_directory_fingerprint(plugin_dir)
    cached_dir_fp = cache.get('dir_fingerprint', '')
    if current_dir_fp != cached_dir_fp:
        logger.info("插件目录已变更，缓存失效", extra={'plugin': 'system'})
        return False

    # 2. 插件状态校验
    cached_status_hash = cache.get('status_hash', '')
    if current_status_hash != cached_status_hash:
        logger.info("插件启用/禁用状态已变更，缓存失效", extra={'plugin': 'system'})
        return False

    # 3. 逐文件指纹校验（精确校验）
    for plugin_info in cache.get('discovered_plugins', []):
        cached_fp = cache.get('fingerprints', {}).get(plugin_info['name'])
        if not cached_fp:
            return False
        filepath = os.path.join(plugin_dir, plugin_info['file'])
        if not os.path.exists(filepath):
            return False
        current_fp = compute_file_fingerprint(filepath)
        if current_fp != cached_fp:
            logger.info(f"插件 {plugin_info['name']} 文件已变更，缓存失效", extra={'plugin': 'system'})
            return False

    return True


def _scan_plugin_module(module_name: str, file_key: str, plugin_dir: str):
    """扫描单个插件模块，返回插件元信息 dict；非插件模块或异常返回 None。"""
    try:
        module = importlib.import_module(module_name)
    except Exception as e:
        logger.error(f"导入插件 {module_name} 失败: {str(e)}", extra={'plugin': 'system'})
        return None
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, type) and \
                any(base.__name__ == 'BasePlugin' for base in attr.__mro__) and \
                attr.__name__ != 'BasePlugin':
            try:
                temp_inst = attr()
            except Exception as e:
                logger.error(f"实例化插件 {module_name} 失败: {str(e)}", extra={'plugin': 'system'})
                return None
            info = {
                'name': temp_inst.name,
                'file': file_key,
                'module_name': module_name,
                'class_name': attr.__name__,
                'dependencies': temp_inst.dependencies,
                'pip_dependencies': getattr(temp_inst, 'pip_dependencies', []) or [],
                'category': getattr(temp_inst, 'category', 'uncategorized'),
                'description': getattr(temp_inst, 'description', ''),
                'version': getattr(temp_inst, 'version', '0.0.0'),
                'title': getattr(temp_inst, 'title', temp_inst.name),
                'author': getattr(temp_inst, 'author', '佚名'),
                'permission': getattr(temp_inst, 'permission', 'user'),
                'require_framework_version': getattr(temp_inst, 'require_framework_version', '')
            }
            # 插件包描述文件（plugins/<name>.json 或 plugins/<name>/<name>.json）为权威：整体覆盖类属性
            # （缺失字段保留类属性兜底，兼容存量无描述文件插件）
            meta_file = plugin_meta_file(global_var.BASE_DIR, temp_inst.name)
            if os.path.isfile(meta_file):
                try:
                    with open(meta_file, 'r', encoding='utf-8') as _mf:
                        meta = json.load(_mf)
                    if isinstance(meta, dict):
                        if meta.get('name') and meta['name'] != temp_inst.name:
                            logger.error(
                                f"插件描述文件 name 与插件类 name 不一致，跳过加载: "
                                f"{meta.get('name')} vs {temp_inst.name}",
                                extra={'plugin': 'system'})
                            return None
                        for _k in META_FIELDS:
                            if _k in meta:
                                info[_k] = meta[_k]
                except (json.JSONDecodeError, UnicodeDecodeError, OSError):
                    # v4.17.2：描述文件失效时告警升级并打标，供后台/调试页提示（否则 json 内
                    # capabilities/require_framework_version 等声明静默丢失，enforce 下莫名失败）
                    info['meta_invalid'] = True
                    logger.error(
                        f"插件描述文件失效，已回退插件类属性（json 内 capabilities/"
                        f"require_framework_version 等声明将被忽略）: {meta_file}",
                        extra={'plugin': 'system'})
                else:
                    info.pop('meta_invalid', None)
            return info
    return None

def scan_plugin_metadata(plugin_dir: str) -> list[dict]:
    """
    仅扫描插件元信息，不加载插件实例。
    双布局发现（v4.21 目录化）：
    - 扁平主文件：plugins/*.py（内置 auth 及历史扁平主文件）→ module=plugins.<name>
    - 目录化主文件：plugins/<name>/<name>.py → module=plugins.<name>.<name>
    返回发现结果列表（info 含 'module_name' 供 loader 直接导入）。
    """
    discovered = []
    _skip_top = ('configs', 'temp', 'data', '__pycache__')
    for fn in sorted(os.listdir(plugin_dir)):
        full = os.path.join(plugin_dir, fn)
        # ---- 扁平主文件：plugins/*.py ----
        if os.path.isfile(full) and fn.endswith('.py') and \
                fn not in ('__init__.py', 'base_plugin.py'):
            info = _scan_plugin_module(f'plugins.{fn[:-3]}', fn, plugin_dir)
            if info:
                discovered.append(info)
            continue
        # ---- 目录化主文件：plugins/<name>/<name>.py ----
        if os.path.isdir(full) and fn not in _skip_top:
            main_py = os.path.join(full, f'{fn}.py')
            if os.path.isfile(main_py):
                file_key = f'plugins/{fn}/{fn}.py'
                info = _scan_plugin_module(f'plugins.{fn}.{fn}', file_key, plugin_dir)
                if info:
                    discovered.append(info)
    return discovered
