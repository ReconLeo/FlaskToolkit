# -*- coding: utf-8 -*-
"""插件启用/禁用状态读写（共享状态保存在 global_var，保持同一对象）"""
import hashlib
import json
import logging
import os

import global_var

logger = logging.getLogger('flask.app')


def load_plugin_status() -> tuple[dict, str]:
    """
    加载插件启用/禁用状态
    返回: (状态字典, 状态哈希)
    """
    global_var.plugin_status.clear()

    if os.path.exists(global_var.PLUGIN_STATUS_FILE):
        try:
            with open(global_var.PLUGIN_STATUS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            global_var.plugin_status.update(data)
        except Exception as e:
            logger.error(f"加载插件状态失败: {str(e)}", extra={'plugin': 'system'})

    # 计算状态哈希（用于缓存校验）
    status_hash = hashlib.sha256(
        json.dumps(global_var.plugin_status, sort_keys=True).encode('utf-8')
    ).hexdigest()

    return global_var.plugin_status, status_hash


def save_plugin_status():
    """保存插件启用/禁用状态"""
    try:
        os.makedirs(os.path.dirname(global_var.PLUGIN_STATUS_FILE), exist_ok=True)
        with open(global_var.PLUGIN_STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(global_var.plugin_status, f, indent=2, ensure_ascii=False)
        logger.info("插件状态已保存", extra={'plugin': 'system'})
    except Exception as e:
        logger.error(f"保存插件状态失败: {str(e)}", extra={'plugin': 'system'})
