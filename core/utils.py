# -*- coding: utf-8 -*-
"""通用工具函数（与原 app.py 中的工具函数对应）"""
import os
import re
import socket

import global_var

# Flask 路径参数模式：<param_name> 或 <converter:param_name>
PATH_PARAM_PATTERN = re.compile(r'<(?:\w+:)?(\w+)>')


def secure_filename_cn(filename):
    """支持中文的安全文件名处理"""
    # 允许中文、字母、数字、下划线、短横线、点
    filename = re.sub(r'[^\w\u4e00-\u9fa5\-\.]', '_', filename)
    # 移除开头的点和斜杠，防止路径遍历
    filename = filename.lstrip('./\\')
    # 空文件名默认值
    if not filename:
        filename = 'untitled'
    return filename


def is_port_available(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return True
        except OSError:
            return False


def get_available_port(start_port=5000, max_port=5100):
    for port in range(start_port, max_port + 1):
        if is_port_available(port):
            return port
    raise RuntimeError(f"没有可用端口（尝试了{start_port}到{max_port}）")


def parse_path_pattern(path: str) -> tuple[re.Pattern, list[str]]:
    """
    将 Flask 风格的路径转换为正则表达式，并提取参数名
    例如: /api/packs/<pack_id> → (re.compile(r'/api/packs/([^/]+)'), ['pack_id'])
    例如: /api/packs/<int:pack_id> → (re.compile(r'/api/packs/(\\d+)'), ['pack_id'])
    """
    param_names = []
    regex_parts = []

    for segment in path.split('/'):
        if not segment:
            continue
        match = PATH_PARAM_PATTERN.match(segment)
        if match:
            param_name = match.group(1)
            param_names.append(param_name)
            # 支持 Flask 的转换器
            if segment.startswith('<int:'):
                regex_parts.append(r'(\d+)')
            elif segment.startswith('<float:'):
                regex_parts.append(r'(\d+\.?\d*)')
            elif segment.startswith('<path:'):
                regex_parts.append(r'(.+)')
            else:
                regex_parts.append(r'([^/]+)')
        else:
            regex_parts.append(segment)

    pattern_str = '/' + '/'.join(regex_parts)
    return re.compile(f'^{pattern_str}$'), param_names


def check_upload_size(file, max_size: int) -> int:
    """
    在保存前检查上传文件大小（基于流 seek/tell，避免先落盘再判断）。
    :param file: Flask request.files 条目（或其 .stream / 任意可 seek 类文件对象）
    :param max_size: 大小上限（字节）
    :return: 超过 max_size 时返回实际大小（字节）；未超限或无法判断时返回 0
    """
    stream = getattr(file, 'stream', None) or file
    try:
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(0)
        if size > max_size:
            return size
    except (OSError, AttributeError):
        # 流不可 seek（如某些代理场景）时跳过，后续仍有 zip 解析兜底
        pass
    return 0

def call_plugin(plugin_name: str, method_name: str, *args, **kwargs):
    """
    全局调用插件方法，供非插件逻辑使用
    """
    if plugin_name not in global_var.plugins:
        raise ValueError(f"插件 {plugin_name} 未加载")
    target_plugin = global_var.plugins[plugin_name]
    if not hasattr(target_plugin, method_name) or method_name.startswith('_'):
        raise ValueError(f"插件 {plugin_name} 不存在公开方法 {method_name}")
    return getattr(target_plugin, method_name)(*args, **kwargs)
