# -*- coding: utf-8 -*-
"""前端工具配置加载（共享状态保存在 global_var.frontend_tools，保持同一对象）"""
import json
import logging
import os

import global_var

logger = logging.getLogger('flask.app')


def load_frontend_tools():
    """加载前端工具配置，增加容错处理"""
    global_var.frontend_tools.clear()
    config_file = os.path.join(global_var.BASE_DIR, 'frontend_tools.json')

    if not os.path.exists(config_file):
        logger.warning("前端工具配置文件不存在，已初始化空列表", extra={'plugin': 'system'})
        return

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"前端工具配置文件解析失败: {str(e)}", extra={'plugin': 'system'})
        return
    except Exception as e:
        logger.error(f"读取前端工具配置文件失败: {str(e)}", extra={'plugin': 'system'})
        return

    if not isinstance(config_data, list):
        logger.error("前端工具配置文件格式错误，应为数组", extra={'plugin': 'system'})
        return

    template_dir = os.path.join(global_var.BASE_DIR, 'templates', 'frontend_tools')
    valid_tools = []

    for tool in config_data:
        if not isinstance(tool, dict):
            logger.warning(f"无效的前端工具配置项，跳过: {tool}", extra={'plugin': 'system'})
            continue

        # 必填字段校验
        name = tool.get('name')
        if not name or not isinstance(name, str):
            logger.warning("前端工具缺少name字段，跳过", extra={'plugin': 'system'})
            continue

        # 校验模板文件是否存在
        template_path = os.path.join(template_dir, f"{name}.html")
        if not os.path.exists(template_path):
            logger.warning(f"前端工具 {name} 的模板文件不存在，跳过", extra={'plugin': 'system'})
            continue

        # 字段容错，设置默认值（新增enabled默认值）
        valid_tool = {
            'name': name,
            'title': tool.get('title', name),  # 缺省用name作为显示名称
            'author': tool.get('author', '佚名'),  # 缺省作者为佚名
            'description': tool.get('description', '暂无描述'),
            'category': tool.get('category', '其他工具'),
            'version': tool.get('version', '1.0.0'),
            'permission': tool.get('permission', 'user'),
            'require_framework_version': tool.get('require_framework_version', ''),
            'enabled': tool.get('enabled', True),  # 缺省为启用状态
            'type': 'frontend'
        }

        valid_tools.append(valid_tool)
        logger.info(f"已加载前端工具: {valid_tool['title']} - {valid_tool['description']}", extra={'plugin': 'system'})

    global_var.frontend_tools.extend(valid_tools)
    logger.info(f"前端工具加载完成，共加载 {len(global_var.frontend_tools)} 个有效工具", extra={'plugin': 'system'})
