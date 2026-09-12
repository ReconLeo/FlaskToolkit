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

    # ========== 主日志格式 ==========
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(plugin)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        defaults={'plugin': 'system'}
    )

    # 运行日志（INFO+）
    info_handler = RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)

    # 错误日志（ERROR+）
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

    handlers = [info_handler, error_handler, console_handler]

    def _attach(logger: logging.Logger):
        """清空并挂载三组 handler，禁止向父 Logger 传播（避免落 lastResort 只进控制台）"""
        logger.handlers.clear()
        logger.propagate = False
        for h in handlers:
            logger.addHandler(h)
        logger.setLevel(logging.INFO)

    # 关键修复（P0#1）：Flask 3.x 下 app.logger 的 logger 名 = 应用 import_name（本框架为 'app'），
    # 不再等于框架 core/routes 模块约定使用的 'flask.app'。若只配置 app.logger，则
    # 'flask.app' 侧所有 .error()/.warning() 会落到 logging.lastResort（仅控制台、无前缀、不进文件），
    # 导致 500/权限/插件页面错误及插件日志全部丢失。故必须对 app.logger 与框架统一使用的
    # 'flask.app' 等 logger 同时挂载 handler。
    _attach(app.logger)                               # Flask 3.1 下实际名为 'app'
    _attach(logging.getLogger('flask.app'))           # 框架 core/routes/plugins 模块统一 logger
    _attach(logging.getLogger('flasktoolkit.events')) # v4.16 事件总线
    _attach(logging.getLogger('routes.admin'))        # 管理路由独立 logger

    # ========== 处理 Werkzeug 默认的 Logger ==========
    # 修复：原先仅挂 StreamHandler(console)，日常 API/页面访问不落盘。现追加文件 handler 到 app.log。
    werkzeug_log = logging.getLogger('werkzeug')
    werkzeug_log.handlers.clear()
    werkzeug_log.propagate = False
    _wf = logging.Formatter(
        '%(asctime)s - %(levelname)s - werkzeug - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    _wfile = RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    _wfile.setLevel(logging.INFO)
    _wfile.setFormatter(_wf)
    _wconsole = logging.StreamHandler()
    _wconsole.setLevel(logging.INFO)
    _wconsole.setFormatter(_wf)
    werkzeug_log.addHandler(_wfile)
    werkzeug_log.addHandler(_wconsole)
    werkzeug_log.setLevel(logging.INFO)

    # ========== 设置根 Logger 级别，避免第三方库 INFO 日志混入 ==========
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)

    return PluginLogAdapter
