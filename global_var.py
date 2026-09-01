"""
全局常量与共享状态（收敛版）

设计原则：
- 本模块只存放【路径常量】与【可变共享状态】，不在此处导入任何第三方库（flask/watchdog/apscheduler 等）。
- 各模块通过 `import global_var` 显式引用（如 `global_var.plugins`），禁止 `from global_var import *`。
- 需要第三方类实例的状态（如 scheduler）由 app 入口创建后赋值给本模块，core 模块引用同一对象。
"""
import os
from typing import Dict, List, Set, Any

# ------------------------------ 基础路径配置 ------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_STATUS_FILE = os.path.join(BASE_DIR, 'plugins', 'status.json')  # 插件启用/禁用状态储存文件路径
STATS_FILE = os.path.join(BASE_DIR, 'data', 'stats.json')  # 统计数据文件路径
# 前端工具上传临时目录
UPLOAD_TEMP_DIR = os.path.join(BASE_DIR, 'temp')
FRONTEND_TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates', 'frontend_tools')
FRONTEND_CONFIG_FILE = os.path.join(BASE_DIR, 'frontend_tools.json')
# 后端插件目录
PLUGIN_CONFIGS_DIR = os.path.join(BASE_DIR, 'plugins', 'configs')  # 配置目录
PLUGIN_TEMP_DIR = os.path.join(BASE_DIR, 'plugins', 'temp')  # 临时文件夹
# 后端插件扫描结果缓存
PLUGIN_CACHE_DIR = os.path.join(BASE_DIR, '.plugin_cache')
PLUGIN_CACHE_FILE = os.path.join(PLUGIN_CACHE_DIR, 'plugin_discovery_cache.json')
CACHE_VERSION = 1  # 缓存格式版本，变更时自动失效
# 日志文件目录
LOG_DIR = os.path.join(BASE_DIR, 'logs')

# ------------------------------ 全局常量 ------------------------------
FRAMEWORK_VERSION = "4.2.2"  # 框架版本（后端插件 require_framework_version 比较基准）
# 内置（系统自带）插件清单：Factory Reset 时受保护不删除
BUILTIN_PLUGINS = ('auth', 'user_manage')
# 管理后台上传包大小上限（后端插件包 .zip / 前端工具包 .zip 统一限制，单位字节）
PACKAGE_MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
# 全局文件上传大小上限（单位字节）：MAX_CONTENT_LENGTH 兜底，插件可用 max_upload_size 覆盖更严/更宽限制
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB
MAX_UPLOAD_SIZE_MB = 100  # 全局默认上传上限（MB，用户可配置）
# 插件包完整性校验模式：strict（缺 manifest/失败均拒绝）/ warn（缺 manifest 告警放行，有则严格校验）/ off（跳过）
PACKAGE_INTEGRITY_MODE = 'warn'
# 可选：插件包签名公钥 PEM 文件路径。配置后安装带 signature 的包时强制验证签名；不配置则跳过签名验证
PLUGIN_PUBLIC_KEY_PEM = ''

# ------------------------------ 用户可配置项（由 CLI 工具 tools/config.py 管理） ------------------------------
# key -> {default, kind, desc}
# kind: path(路径) / str / int / bool / enum(choices)
CONFIG_ITEMS = {
    'UPLOAD_TEMP_DIR': {'default': os.path.join(BASE_DIR, 'temp'), 'kind': 'path',
                        'desc': '前端工具上传临时目录'},
    'FRONTEND_TEMPLATE_DIR': {'default': os.path.join(BASE_DIR, 'templates', 'frontend_tools'), 'kind': 'path',
                              'desc': '前端工具模板/静态资源目录'},
    'FRONTEND_CONFIG_FILE': {'default': os.path.join(BASE_DIR, 'frontend_tools.json'), 'kind': 'path',
                             'desc': '前端工具注册配置文件'},
    'PLUGIN_CONFIGS_DIR': {'default': os.path.join(BASE_DIR, 'plugins', 'configs'), 'kind': 'path',
                           'desc': '插件配置目录'},
    'PLUGIN_TEMP_DIR': {'default': os.path.join(BASE_DIR, 'plugins', 'temp'), 'kind': 'path',
                        'desc': '插件临时目录'},
    'PLUGIN_CACHE_DIR': {'default': os.path.join(BASE_DIR, '.plugin_cache'), 'kind': 'path',
                         'desc': '插件扫描缓存目录'},
    'LOG_DIR': {'default': os.path.join(BASE_DIR, 'logs'), 'kind': 'path', 'desc': '日志目录'},
    'STATS_FILE': {'default': os.path.join(BASE_DIR, 'data', 'stats.json'), 'kind': 'path',
                   'desc': '统计数据文件'},
    'PACKAGE_MAX_UPLOAD_SIZE_MB': {'default': 10, 'kind': 'int',
                                   'desc': '插件包/工具包上传大小上限（MB，映射 PACKAGE_MAX_UPLOAD_SIZE）'},
    'MAX_UPLOAD_SIZE_MB': {'default': 100, 'kind': 'int',
                           'desc': '全局文件上传大小上限（MB，映射 MAX_UPLOAD_SIZE，MAX_CONTENT_LENGTH 兜底）'},
    'PLUGIN_STRICT_MODE': {'default': False, 'kind': 'bool',
                           'desc': '严格模式：on_load 依赖检查降级由 on_ready 钩子延后（所有插件加载完成后执行）'},
    'PACKAGE_INTEGRITY_MODE': {'default': 'warn', 'kind': 'enum',
                               'choices': ['strict', 'warn', 'off'],
                               'desc': '插件包完整性校验模式'},
    'PLUGIN_PUBLIC_KEY_PEM': {'default': '', 'kind': 'path',
                              'desc': '插件签名公钥 PEM 文件路径（配置后强制验签）'},
    'HOST': {'default': '127.0.0.1', 'kind': 'str', 'desc': '服务绑定地址（环境变量 FLASKTOOLKIT_HOST 优先）'},
    'PORT': {'default': '', 'kind': 'int', 'desc': '服务端口（留空自动探测，环境变量 FLASKTOOLKIT_PORT 优先）'},
    'DEBUG': {'default': False, 'kind': 'bool',
              'desc': '调试模式（环境变量 FLASKTOOLKIT_DEBUG 优先）'},
}

USER_CONFIG_FILE = os.path.join(BASE_DIR, 'data', 'user_config.json')
_user_config: Dict[str, Any] = {}


def coerce_config_value(value: Any, item: Dict) -> Any:
    """按配置项类型转换并校验；非法返回 None"""
    kind = item['kind']
    if kind == 'int':
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    if kind == 'bool':
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ('1', 'true', 'yes', 'on')
    if kind == 'enum':
        return value if value in item.get('choices', []) else None
    return str(value)


def get_user_config() -> Dict[str, Any]:
    """返回用户配置合并默认值后的完整视图"""
    merged = {k: v['default'] for k, v in CONFIG_ITEMS.items()}
    merged.update(_user_config)
    return merged


def load_user_config():
    """从 data/user_config.json 加载用户配置并覆盖默认常量（路径/选项）。
    优先级：用户配置文件 > 默认值；HOST/PORT/DEBUG 的环境变量在 app 启动时再覆盖。
    本模块设计原则：不在此处导入第三方库，json 为局部导入。"""
    global _user_config
    _user_config = {}
    try:
        import json
        if os.path.exists(USER_CONFIG_FILE):
            with open(USER_CONFIG_FILE, encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                _user_config = data
    except Exception:
        _user_config = {}
    # 应用：覆盖路径/选项常量（HOST/PORT/DEBUG 由 app 启动时读取 _user_config）
    for key, value in _user_config.items():
        if key not in CONFIG_ITEMS:
            continue
        converted = coerce_config_value(value, CONFIG_ITEMS[key])
        if converted is None:
            continue
        if key == 'PACKAGE_MAX_UPLOAD_SIZE_MB':
            globals()['PACKAGE_MAX_UPLOAD_SIZE'] = int(converted) * 1024 * 1024
        elif key == 'MAX_UPLOAD_SIZE_MB':
            globals()['MAX_UPLOAD_SIZE'] = int(converted) * 1024 * 1024
            globals()['MAX_UPLOAD_SIZE_MB'] = int(converted)
        elif key not in ('HOST', 'PORT', 'DEBUG'):
            globals()[key] = converted
    # 依赖联动：PLUGIN_CACHE_DIR 变更时同步 PLUGIN_CACHE_FILE
    if 'PLUGIN_CACHE_DIR' in _user_config:
        globals()['PLUGIN_CACHE_FILE'] = os.path.join(
            globals()['PLUGIN_CACHE_DIR'], 'plugin_discovery_cache.json')


# ------------------------------ 共享状态（由各模块/入口赋值） ------------------------------
# Flask 实例（app 入口创建后赋值）
app = None

# 日志系统是否已初始化全局标记
logging_config = {
    'initialized': False
}

# 插件相关
plugins: Dict[str, Any] = {}  # 全局插件注册中心 {插件名: 插件实例}（plugin_loader 维护）
plugin_categories: Dict[str, List] = {}
loaded_module_names: Set[str] = set()
plugin_status: Dict[str, Dict] = {}  # 插件启用/禁用状态
plugin_catalog: List[Dict] = []  # 插件目录（含禁用/未加载，供首页/管理页直接读取，避免每次请求扫描磁盘）

# 定时任务调度器（app 入口创建 BackgroundScheduler 后赋值，core 模块引用同一对象）
scheduler = None

# 统计相关
call_stats: Dict[str, int] = {}  # 接口调用统计
frontend_access_stats: Dict[str, int] = {}  # 前端工具页面访问统计

# 前端工具
frontend_tools: List[Dict] = []
