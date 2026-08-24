# -*- coding: utf-8 -*-
"""访问统计：加载、保存、计数（共享状态保存在 global_var，保持同一对象避免引用失效）"""
import json
import logging
import os
from datetime import datetime

import global_var

logger = logging.getLogger('flask.app')


def load_stats():
    """加载统计数据（清空并原地回填，保持 global_var 中字典对象不变）"""
    global_var.call_stats.clear()
    global_var.frontend_access_stats.clear()

    if not os.path.exists(global_var.STATS_FILE):
        save_stats()
        return

    try:
        with open(global_var.STATS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        global_var.call_stats.update(data.get('call_stats', {}))
        global_var.frontend_access_stats.update(data.get('frontend_access_stats', {}))
    except Exception as e:
        logger.error(f"加载统计数据失败: {str(e)}", extra={'plugin': 'system'})


def save_stats():
    """保存统计数据到文件"""
    try:
        data = {
            "call_stats": global_var.call_stats,
            "frontend_access_stats": global_var.frontend_access_stats,
            "last_update": datetime.now().isoformat()
        }
        # 确保数据目录存在（首次启动时 __main__ 尚未执行目录创建）
        os.makedirs(os.path.dirname(global_var.STATS_FILE), exist_ok=True)
        with open(global_var.STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存统计数据失败: {str(e)}", extra={'plugin': 'system'})


def increment_call_stats(plugin_name, endpoint):
    """增加API调用统计（内存中计数，定时批量保存）"""
    key = f"{plugin_name}:{endpoint}"
    global_var.call_stats[key] = global_var.call_stats.get(key, 0) + 1


def increment_frontend_access(tool_name):
    """增加前端工具访问统计（内存中计数，定时批量保存）"""
    key = f"frontend:{tool_name}"
    global_var.frontend_access_stats[key] = global_var.frontend_access_stats.get(key, 0) + 1
