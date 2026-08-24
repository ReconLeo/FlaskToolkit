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
from core.plugin_pack import META_FIELDS
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


def compute_directory_fingerprint(plugin_dir: str) -> str:
    """
    计算插件目录的整体指纹
    包含：目录下所有 .py 文件的相对路径 + 对应指纹
    用于快速判断是否有新增/删除/修改文件
    """
    hasher = hashlib.sha256()

    def _is_plugin_file(name: str) -> bool:
        # 主插件 .py（排除基类/包初始化）或插件包描述文件 plugins/<name>.json
        if name.endswith('.py') and name not in ['__init__.py', 'base_plugin.py']:
            return True
        if name.endswith('.json') and name not in ['status.json']:
            return True
        return False

    # 收集所有插件文件信息
    plugin_files = []
    for filename in sorted(os.listdir(plugin_dir)):
        if not _is_plugin_file(filename):
            continue
        filepath = os.path.join(plugin_dir, filename)
        if os.path.isfile(filepath):
            fingerprint = compute_file_fingerprint(filepath)
            plugin_files.append(f"{filename}:{fingerprint}")

    # 将文件名列表本身也纳入指纹（用于检测新增/删除）
    file_list_str = ",".join(
        f for f in sorted(os.listdir(plugin_dir))
        if _is_plugin_file(f)
    )
    hasher.update(file_list_str.encode('utf-8'))
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


def scan_plugin_metadata(plugin_dir: str) -> list[dict]:
    """
    仅扫描插件元信息，不加载插件实例
    返回发现结果列表
    """
    discovered = []

    for filename in os.listdir(plugin_dir):
        if not (filename.endswith('.py') and filename not in ['__init__.py', 'base_plugin.py']):
            continue

        module_name = f'plugins.{filename[:-3]}'
        try:
            module = importlib.import_module(module_name)
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type):
                    if any(base.__name__ == 'BasePlugin' for base in attr.__mro__) and attr.__name__ != 'BasePlugin':
                        temp_inst = attr()
                        info = {
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
                        # 插件包描述文件（plugins/<name>.json）为权威：整体覆盖类属性
                        # （缺失字段保留类属性兜底，兼容存量无描述文件插件）
                        meta_file = os.path.join(plugin_dir, f"{temp_inst.name}.json")
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
                                        continue
                                    for _k in META_FIELDS:
                                        if _k in meta:
                                            info[_k] = meta[_k]
                            except (json.JSONDecodeError, UnicodeDecodeError, OSError):
                                logger.warning(f"读取插件描述文件失败，忽略: {meta_file}", extra={'plugin': 'system'})
                        discovered.append(info)
        except Exception as e:
            logger.error(f"扫描插件 {filename} 元信息失败: {str(e)}", extra={'plugin': 'system'})

    return discovered
