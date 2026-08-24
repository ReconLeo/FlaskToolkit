# -*- coding: utf-8 -*-
"""日志系统初始化与插件日志适配器"""
import logging
import os
from logging.handlers import RotatingFileHandler

import global_var


class PluginLogAdapter(logging.LoggerAdapter):
    """插件专属日志适配器：自动为日志附加插件标识"""

    def process(self, msg, kwargs):
        if 'extra' not in kwargs:
            kwargs['extra'] = {}
        kwargs['extra'].update(self.extra)
        return msg, kwargs


def setup_logging(app):
    """
    初始化 app 日志系统，返回 PluginLogAdapter 类。
    幂等：重复调用直接返回已建适配器，避免 Handler 重复追加。
    """
    # ========== 幂等性保护 ==========
    if global_var.logging_config['initialized']:
        app.logger.warning("日志系统已初始化，跳过重复配置", extra={'plugin': 'system'})
        return PluginLogAdapter
    global_var.logging_config['initialized'] = True

    log_dir = os.path.join(global_var.BASE_DIR, 'logs')
    os.makedirs(log_dir, exist_ok=True)

    # ========== 清除 app.logger 上已有的所有 Handler ==========
    app.logger.handlers.clear()

    # ========== 禁止日志向父 Logger 传播 ==========
    app.logger.propagate = False

    # 主日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(plugin)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        defaults={'plugin': 'system'}
    )

    # 运行日志
    info_handler = RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)

    # 错误日志
    error_handler = RotatingFileHandler(
        os.path.join(log_dir, 'error.log'),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    app.logger.addHandler(info_handler)
    app.logger.addHandler(error_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.INFO)

    # ========== 处理 Werkzeug 默认的 Logger ==========
    werkzeug_log = logging.getLogger('werkzeug')
    werkzeug_log.handlers.clear()
    werkzeug_log.propagate = False
    werkzeug_handler = logging.StreamHandler()
    werkzeug_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - werkzeug - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    werkzeug_log.addHandler(werkzeug_handler)
    werkzeug_log.setLevel(logging.INFO)

    # ========== 设置根 Logger 级别，避免第三方库 INFO 日志混入 ==========
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)

    return PluginLogAdapter
