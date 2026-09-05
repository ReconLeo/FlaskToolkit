# ------------------------------ 标准库 ------------------------------
import os
import sys

# ------------------------------ 第三方库 ------------------------------
from flask import Flask
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler

# ------------------------------ 全局常量与共享状态（显式导入，不再 import *） ------------------------------
import global_var
from global_var import (
    PLUGIN_CONFIGS_DIR, PLUGIN_TEMP_DIR, LOG_DIR, STATS_FILE, UPLOAD_TEMP_DIR,
    plugins,
)

# ------------------------------ core 服务层 ------------------------------
from core.logging_setup import setup_logging, PluginLogAdapter
from core.stats import load_stats, save_stats
from core.frontend_tools import load_frontend_tools
from core.plugin_loader import load_plugins
from core.utils import get_available_port, is_port_available
from core.watcher import start_file_watcher
from routes import register_routes

# 初始化 Flask 实例
app = Flask(__name__)
# 模板自动重载：前端工具/插件 html 更新后即时生效（配合 watcher 热重载，无需重启服务）
app.config['TEMPLATES_AUTO_RELOAD'] = True
# 全局文件上传大小兜底（MAX_UPLOAD_SIZE 默认 100MB，可经 config CLI 调整；插件可用 max_upload_size/route max_upload 覆盖更严或更宽限制）
app.config['MAX_CONTENT_LENGTH'] = global_var.MAX_UPLOAD_SIZE
global_var.app = app  # 同步回全局状态，供 core 模块引用
CORS(app, supports_credentials=True)

# 定时任务调度器：创建后注入 global_var（core/plugin_loader 引用同一对象）
scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
global_var.scheduler = scheduler
 
PluginLogAdapter = setup_logging(app)
load_stats()  # 新增：启动时加载历史统计数据


# ------------------------------ 路由注册（routes 包） ------------------------------
register_routes(app)

# v4.7.0：Jinja 模板全局注入（system_name/system_version/project_github 等，供所有页面/后台使用）
# 注册在模块顶层：测试环境直接导入 app 即可生效；内部动态读取用户配置，启动后配置变更亦生效
@app.context_processor
def inject_system_info():
    _ucfg = global_var.get_user_config()
    return {
        'system_name': _ucfg.get('SYSTEM_NAME') or global_var.PROJECT_NAME,
        'system_version': _ucfg.get('SYSTEM_VERSION_LABEL') or 'v' + global_var.FRAMEWORK_VERSION,
        'project_github': global_var.PROJECT_GITHUB,
        'project_name': global_var.PROJECT_NAME,
        'project_author': global_var.PROJECT_AUTHOR,
        'project_slogan': global_var.PROJECT_SLOGAN,
    }

# v4.9.0：i18n 全局注入（t 翻译函数 + lang 当前语言 + available_langs 可用语言列表）
# 语言解析：Cookie lang > 用户配置 LANGUAGE > 默认 zh-CN；插件可带 locales/<lang>.json 合并
@app.context_processor
def inject_i18n():
    from core import i18n
    from flask import request
    lang = i18n.get_lang()
    tr = i18n.make_translator(lang)
    i18n.set_current_translator(tr)
    return {
        't': tr,
        'lang': lang,
        'available_langs': i18n.available_languages(),
        't_json': tr.table,          # 当前语言完整翻译表（前端 window.T 使用）
    }

@app.context_processor
def inject_system_info():
    _ucfg = global_var.get_user_config()
    return {
        'system_name': _ucfg.get('SYSTEM_NAME') or global_var.PROJECT_NAME,
        'system_version': _ucfg.get('SYSTEM_VERSION_LABEL') or 'v' + global_var.FRAMEWORK_VERSION,
        'project_github': global_var.PROJECT_GITHUB,
        'project_name': global_var.PROJECT_NAME,
        'project_author': global_var.PROJECT_AUTHOR,
        'project_slogan': global_var.PROJECT_SLOGAN,
    }

# 注册应用关闭钩子，确保服务停止前保存最新统计数据
@app.teardown_appcontext
def save_stats_on_shutdown(exception=None):
    save_stats()
    if exception:
        app.logger.error(f"应用关闭时发生异常: {str(exception)}", extra={'plugin': 'system'})

# 全局停止钩子，调用所有插件的on_shutdown方法
import atexit
import signal
import sys
 
# 标记是否已经执行过停止逻辑，避免重复执行
_shutdown_executed = False
 
def on_server_shutdown(signal_num=None, frame=None):
    """服务停止前执行"""
    global _shutdown_executed
    if _shutdown_executed:
        return
    
    _shutdown_executed = True
    app.logger.info("服务正在停止，通知所有插件处理退出逻辑...", extra={'plugin': 'system'})
    
    # 遍历所有已加载插件，调用停止钩子
    for plugin_name, plugin in plugins.items():
        try:
            app.logger.debug(f"通知插件 {plugin_name} 停止...", extra={'plugin': 'system'})
            plugin.on_shutdown()
            app.logger.info(f"插件 {plugin_name} 已完成停止前处理", extra={'plugin': 'system'})
        except Exception as e:
            app.logger.error(f"插件 {plugin_name} 停止处理失败: {str(e)}", extra={'plugin': 'system'})
    
    app.logger.info("所有插件停止处理完成，正在退出...", extra={'plugin': 'system'})
    
    # 强制终止进程，避免Flask/scheduler继续运行
    os._exit(0)  # 见 on_server_shutdown 注释：atexit 中 sys.exit 会打印警告并可能污染退出码
 
# 注册停止钩子
atexit.register(on_server_shutdown)
# 捕获系统停止信号
try:
    signal.signal(signal.SIGINT, on_server_shutdown)   # Ctrl+C触发
    signal.signal(signal.SIGTERM, on_server_shutdown)  # 系统停止触发
except:
    # Windows系统不支持部分信号，忽略即可
    pass

if __name__ == '__main__':
    import shutil

    # ===== 用户配置加载（tools/config.py 管理）+ 框架完整性自校验 =====
    from global_var import load_user_config
    load_user_config()

    # ===== v4.7.0：启动横幅（宣传项目信息与 GitHub 链接）=====
    _ucfg = global_var.get_user_config()
    _sys_name = _ucfg.get('SYSTEM_NAME') or global_var.PROJECT_NAME
    _sys_ver = _ucfg.get('SYSTEM_VERSION_LABEL') or ('v' + global_var.FRAMEWORK_VERSION)
    print('-' * 60, flush=True)
    print(f"  {_sys_name}  {_sys_ver}", flush=True)
    print(f"  {global_var.PROJECT_SLOGAN}", flush=True)
    print(f"  框架版本: v{global_var.FRAMEWORK_VERSION}   作者: {global_var.PROJECT_AUTHOR}", flush=True)
    print(f"  GitHub: {global_var.PROJECT_GITHUB}", flush=True)
    print('-' * 60, flush=True)

    # ===== v4.8.0：版本检查（有缓存直接展示；无缓存由后台线程检查，下次启动/后台刷新可见）=====
    if _ucfg.get('UPDATE_CHECK_ENABLED'):
        try:
            from core.update_checker import check_for_update, is_newer, _read_cache
            _upd = check_for_update()
            if _upd is not None and _upd.latest_version:
                if is_newer(_upd.latest_version, global_var.FRAMEWORK_VERSION):
                    print(f"  [更新] 发现新版本 v{_upd.latest_version}"
                          f"（当前 v{global_var.FRAMEWORK_VERSION}，变更 {len(_upd.changes)} 条，"
                          f"详见 tools/update.py --help）", flush=True)
                else:
                    print(f"  [更新] 已是最新版本 v{global_var.FRAMEWORK_VERSION}", flush=True)
            else:
                # 无缓存且拉取失败：静默（后台线程会再试并写缓存）
                pass
        except Exception:
            pass

    # 重新读取配置后的路径常量（顶部 from global_var import 为模块加载时绑定，需刷新）
    PLUGIN_CONFIGS_DIR, PLUGIN_TEMP_DIR, LOG_DIR, STATS_FILE, UPLOAD_TEMP_DIR = (
        global_var.PLUGIN_CONFIGS_DIR, global_var.PLUGIN_TEMP_DIR, global_var.LOG_DIR,
        global_var.STATS_FILE, global_var.UPLOAD_TEMP_DIR)
    from core.selfcheck import run_selfcheck
    _self = run_selfcheck(verbose=False)
    for _f in _self['fatal']:
        print(f"[自检] 致命: {_f}", flush=True)
    for _w in _self['warnings']:
        app.logger.warning(f"自检警告: {_w}", extra={'plugin': 'system'})
    if not _self['ok']:
        print("[自检] 框架完整性自校验失败，中止启动。请根据上方提示修复（缺失文件/依赖）。", flush=True)
        sys.exit(1)
    if _self['first_run']:
        print("[自检] 首次启动：完整性自检通过，框架已初始化。", flush=True)

    # 创建运行所需的目录
    # 变量已于global_var.py声明
    os.makedirs(PLUGIN_CONFIGS_DIR, exist_ok=True)
    os.makedirs(PLUGIN_TEMP_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
    os.makedirs(UPLOAD_TEMP_DIR, exist_ok=True)
    
    # 运行时审计钩子（v4.4.0）：在插件加载前安装，插件模块级顶层代码执行亦纳入审计
    from core.audit_hook import install_audit_hook
    install_audit_hook(global_var.AUDIT_HOOK_MODE)

    scheduler.start()

    # ===== v4.8.0：后台线程执行版本检查（不阻塞启动；结果写入 data/cache/update_check.json）=====
    if global_var.get_user_config().get('UPDATE_CHECK_ENABLED'):
        try:
            import threading
            from core.update_checker import background_check
            threading.Thread(target=background_check, daemon=True, name='update-check').start()
        except Exception:
            pass

    load_plugins()
    load_frontend_tools()
    watcher = start_file_watcher()
    
    # ===== 阶段二-B：运行配置环境变量化（默认安全），用户配置兜底 =====
    _ucfg = global_var.get_user_config()
    # 绑定地址：FLASKTOOLKIT_HOST > user_config.HOST > 默认 127.0.0.1（不暴露局域网）
    host = os.environ.get('FLASKTOOLKIT_HOST', '').strip() or str(_ucfg.get('HOST') or '') or '127.0.0.1'
    # 端口：FLASKTOOLKIT_PORT > user_config.PORT；未指定或端口被占用时自动探测可用端口
    port_env = (os.environ.get('FLASKTOOLKIT_PORT', '').strip()
                or str(_ucfg.get('PORT') or '')).strip()
    if port_env:
        try:
            port_env = int(port_env)
        except ValueError:
            port_env = None
    if port_env and is_port_available(port_env):
        port = port_env
    else:
        if port_env:
            app.logger.warning(f"指定端口 {port_env} 不可用或已被占用，自动探测可用端口", extra={'plugin': 'system'})
        port = get_available_port()
    # 调试模式：FLASKTOOLKIT_DEBUG > user_config.DEBUG，默认关闭（生产安全）
    _dbg_env = os.environ.get('FLASKTOOLKIT_DEBUG', '').strip().lower()
    debug_mode = (_dbg_env in ('1', 'true', 'yes', 'on')) if _dbg_env else bool(_ucfg.get('DEBUG'))
    app.debug = debug_mode  # 同步 app.debug，影响模板自动重载等
    # HTTPS 支持（v4.5.0）：SSL_CERT_FILE/SSL_KEY_FILE 均配置且文件存在时启用 HTTPS（默认 HTTP）
    ssl_context = None
    ssl_cert = global_var.SSL_CERT_FILE
    ssl_key = global_var.SSL_KEY_FILE
    if ssl_cert and ssl_key:
        if os.path.exists(ssl_cert) and os.path.exists(ssl_key):
            ssl_context = (ssl_cert, ssl_key)
            app.logger.info(f"服务启动地址: https://{host}:{port} (HTTPS, debug={debug_mode})", extra={'plugin': 'system'})
        else:
            app.logger.warning(f"已配置 SSL_CERT_FILE/SSL_KEY_FILE 但文件不存在（{ssl_cert} / {ssl_key}），回退 HTTP 启动；可使用 tools/gen_cert.py 生成自签名证书", extra={'plugin': 'system'})
            app.logger.info(f"服务启动地址: http://{host}:{port} (debug={debug_mode})", extra={'plugin': 'system'})
    elif ssl_cert or ssl_key:
        app.logger.warning("SSL_CERT_FILE 与 SSL_KEY_FILE 需同时配置才启用 HTTPS，当前仅配置一项，回退 HTTP 启动", extra={'plugin': 'system'})
        app.logger.info(f"服务启动地址: http://{host}:{port} (debug={debug_mode})", extra={'plugin': 'system'})
    else:
        app.logger.info(f"服务启动地址: http://{host}:{port} (debug={debug_mode})", extra={'plugin': 'system'})

    # 把初始化后的app回写到global模块（确保其他地方导入的是同一个实例）
    import global_var
    global_var.app = app

    try:
        app.run(host=host, port=port, debug=debug_mode, use_reloader=False, ssl_context=ssl_context)
    except KeyboardInterrupt:
        # 捕获Ctrl+C，主动调用停止逻辑
        on_server_shutdown()
    finally:
        # 停止核心组件（移动到这里执行，确保在进程退出前完成）
        if scheduler.running:
            scheduler.shutdown(wait=False)  # wait=False不等待执行中的任务
        watcher.stop()
        watcher.join()
        
        # 临时文件清理逻辑保持不变
        temp_root = PLUGIN_TEMP_DIR
        app.logger.info("正在清理临时文件...", extra={'plugin': 'system'})
        try:
            for item in os.listdir(temp_root):
                item_path = os.path.join(temp_root, item)
                try:
                    if os.path.isfile(item_path) or os.path.islink(item_path):
                        os.unlink(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                except Exception as e:
                    app.logger.warning(f"清理临时项失败 {item_path}: {str(e)}", extra={'plugin': 'system'})
            
            # 清理插件自定义临时目录
            for plugin_name, plugin in plugins.items():
                try:
                    plugin_temp_dir = plugin.get_temp_dir()
                    if not os.path.commonprefix([plugin_temp_dir, temp_root]) == temp_root:
                        if os.path.exists(plugin_temp_dir):
                            shutil.rmtree(plugin_temp_dir)
                            app.logger.info(f"已清理插件 {plugin_name} 自定义临时目录: {plugin_temp_dir}", extra={'plugin': 'system'})
                except Exception as e:
                    app.logger.warning(f"清理插件 {plugin_name} 临时目录失败: {str(e)}", extra={'plugin': 'system'})
                    
        except Exception as e:
            app.logger.error(f"临时文件清理失败: {str(e)}", extra={'plugin': 'system'})