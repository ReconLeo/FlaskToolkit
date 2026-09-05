# -*- coding: utf-8 -*-
"""运行时审计钩子（v4.4.0，安全强化 P1 阶段三）

基于 CPython 原生 sys.addaudithook 建立运行时防线：敏感操作发生时定位调用栈的
plugins/ 来源，按该插件 4.3.2 注册的 capabilities 授权判定，实现"网络白名单=防火墙"
与对静态分析的兜底。

模式 AUDIT_HOOK_MODE（global_var）：
- off：不安装钩子（零开销）
- observe（默认）：未授权行为聚合计数 + 后台线程写审计日志（JSONL），不阻断
- enforce：未授权行为抛 RuntimeError 阻断 + 审计

设计约束（v2 设计稿 + 审计意见）：
- hook 内零 IO（open/logging/网络均禁止，防 audit 递归）；审计写入走后台线程
- 归属判定：栈遍历找 plugins/<name>.py 帧；base_plugin 等框架内置帧不计为插件来源
- 未授权统计按插件分组聚合（_VIOLATIONS），供 /api/admin/stats 返回，
  管理后台按插件展示、合计由前端完成；每条记录携带可复制的建议声明
  （core.capabilities.suggest_for_action，与安装期交叉校验共用生成器）
- 自属路径隐式豁免由 check_filesystem 内置（configs/data/temp 免声明）
"""
import os
import sys
import threading
import time

import global_var

from core import capabilities as caps_mod
from core import quota as _quota_mod

_local = threading.local()

# ------------------------------ 关注事件表 ------------------------------

# open 事件的读写判定
_READ_CHARS = 'r'
_WRITE_CHARS = 'wax+'
_OS_WRONLY = getattr(os, 'O_WRONLY', 1)
_OS_RDWR = getattr(os, 'O_RDWR', 2)
_OS_CREAT = getattr(os, 'O_CREAT', 0x100)
_OS_APPEND = getattr(os, 'O_APPEND', 0x400)
_OS_TRUNC = getattr(os, 'O_TRUNC', 0x200)

# 事件 → (domain, 目标提取函数)
def _open_target(args):
    path = str(args[0])
    mode = args[1] if len(args) > 1 else None
    flags = args[2] if len(args) > 2 else 0
    if isinstance(mode, str):
        if any(c in mode for c in _WRITE_CHARS):
            return 'filesystem:write', path
        if 'r' in mode:
            return 'filesystem:read', path
        return 'filesystem:read', path
    # mode 为 None/int（flags 模式）：写标记任一存在即视为写
    if flags & (_OS_WRONLY | _OS_RDWR | _OS_CREAT | _OS_APPEND | _OS_TRUNC):
        return 'filesystem:write', path
    return 'filesystem:read', path


def _system_target(args):
    return 'process:exec', ''


def _popen_target(args):
    exe = args[0] if args else ''
    if not exe and len(args) > 1 and args[1]:
        exe = args[1][0] if isinstance(args[1], (list, tuple)) else args[1]
    return 'process:exec', os.path.basename(str(exe)).lower() if exe else ''


def _connect_target(args):
    # 真实事件参数为 (socket对象, address)；直接分派时可能传 (address,)
    addr = args[1] if len(args) > 1 else (args[0] if args else ())
    host, port = None, None
    if isinstance(addr, (tuple, list)) and len(addr) >= 2:
        host, port = addr[0], addr[1]
    elif isinstance(addr, str):
        host, port = addr, None
    if isinstance(host, bytes):
        host = host.decode('utf-8', 'replace')
    if host is None:
        return None, None
    ep = f'tcp://{host}' + (f':{port}' if port else '')
    return 'network:tcp', ep


def _bind_target(args):
    # 真实事件参数为 (socket对象, address)；server 声明存在即可（不比对端口）
    return 'network:server', ''


def _path_target(args):
    return 'filesystem:write', str(args[0] if args else '')


def _sqlite_target(args):
    return 'database:sqlite', str(args[0] if args else '')


_EVENTS = {
    'open': _open_target,
    'io.open': _open_target,
    'os.system': _system_target,
    'subprocess.Popen': _popen_target,
    'os.exec': _popen_target,
    'os.execv': _popen_target,
    'os.execve': _popen_target,
    'os.spawn': _popen_target,
    'socket.connect': _connect_target,
    'socket.bind': _bind_target,
    'os.remove': _path_target,
    'os.unlink': _path_target,
    'os.rmdir': _path_target,
    'shutil.rmtree': _path_target,
    'os.mkdir': _path_target,
    'os.makedirs': _path_target,
    'sqlite3.connect': _sqlite_target,
}

# 不需要可执行名比对的域（check_process 传 None = 任意 process:exec 授权）
_ANY_PROCESS = True

# ------------------------------ 状态 ------------------------------

_INSTALLED = False
_MODE = 'off'
_VIOLATIONS = {}          # {plugin: {capability: {'count': n, 'example': str}}}
_PENDING = []             # [(action, plugin, result, detail), ...] 待后台落盘
_PENDING_LOCK = threading.Lock()
_FLUSHER = None


# ------------------------------ 归属判定 ------------------------------

def _norm_slash(p):
    return str(p).replace('\\', '/')


_SYS_PREFIX = _norm_slash(os.path.abspath(sys.base_prefix)) + '/'


# v4.5.0: 框架管理目录（插件经框架 logger/stats/备份机制写入，非插件业务，不归因拦截）
# 懒初始化：LOG_DIR 等可能在 load_user_config 后被覆盖，首次判定时取当前值
_FRAMEWORK_DIRS = None


def _framework_dirs():
    """返回框架运行时管理目录前缀列表（logs/data/backups/temp）"""
    global _FRAMEWORK_DIRS
    if _FRAMEWORK_DIRS is None:
        base = global_var.BASE_DIR
        _FRAMEWORK_DIRS = [
            _norm_slash(os.path.abspath(global_var.LOG_DIR)),
            _norm_slash(os.path.abspath(os.path.join(base, 'data'))),
            _norm_slash(os.path.abspath(os.path.join(base, 'backups'))),
            _norm_slash(os.path.abspath(os.path.join(base, 'temp'))),
        ]
    return _FRAMEWORK_DIRS


def _is_framework_path(path):
    """框架管理目录（logs/data/backups/temp）——插件经框架 logger/stats 等机制写入，非插件业务"""
    norm = _norm_slash(os.path.abspath(str(path)))
    return any(norm.startswith(d + '/') or norm == d for d in _framework_dirs())


def _is_interpreter_path(path):
    """Python 解释器内部路径（stdlib/site-packages/编码器缓存）——插件业务无关，跳过"""
    norm = _norm_slash(os.path.abspath(str(path)))
    return norm.startswith(_SYS_PREFIX) or '/__pycache__/' in norm


# 框架导入插件的唯二入口（scan_plugin_metadata / load_plugins 内的 import_module）：
# 调用栈中出现这些帧，说明 open/import 等事件属框架加载链路，不归因插件。
_FRAMEWORK_LOADER_MARKERS = (
    _norm_slash(os.path.join('core', 'plugin_cache.py')),
    _norm_slash(os.path.join('core', 'plugin_loader.py')),
)


def _module_defines_plugin_class(frame) -> bool:
    """该栈帧所在模块是否定义了 BasePlugin 子类（即插件主模块）。
    插件包辅助模块（corp_utils.py 等）不定义插件类——需向上归因到主插件，
    否则辅助模块被当作独立插件名，主插件自属路径隐式豁免将不生效。"""
    try:
        for v in frame.f_globals.values():
            if isinstance(v, type) and v.__name__ != 'BasePlugin':
                try:
                    mro = v.__mro__
                except Exception:
                    continue
                if any(b.__name__ == 'BasePlugin' for b in mro):
                    return True
    except Exception:
        pass
    return False


def _locate_plugin():
    """遍历调用栈，定位 plugins/<name>.py 最近帧的插件名。
    base_plugin（框架内置）不视为插件来源；无插件帧返回 None（放行）。

    v4.6.0 修复（enforce 下插件无法加载/辅助模块误归因）：
    1) 框架自身扫描/加载插件时（core/plugin_cache.scan_plugin_metadata /
       core/plugin_loader.load_plugins 经 importlib.import_module 导入插件），
       模块顶层 `from plugins.base_plugin import ...` 触发 open(base_plugin.py)，
       调用栈同时含 core/plugin_cache.py（或 plugin_loader.py）与 plugins/<name>.py
       帧——若只按 /plugins/ 匹配会把框架加载读取误归因为插件，enforce 下任何
       插件安装/加载都会被未声明 filesystem:read 拒绝 → 栈中含加载器帧即放行。
    2) 插件包辅助模块（corp_utils.py 等，无 BasePlugin 子类）被误归因为独立插件名，
       使主插件自属路径（plugins/data/<name>/、plugins/configs/<name>.json）隐式豁免
       失效 → 优先归因"定义了 BasePlugin 子类"的最近帧；全部无插件类时回退最近帧。
    """
    found = []
    frame = sys._getframe(1)
    while frame is not None:
        fname = frame.f_globals.get('__file__')
        if fname:
            norm = _norm_slash(fname)
            # 1) 框架加载链路：栈中存在加载器帧 → 框架行为，不归因
            for m in _FRAMEWORK_LOADER_MARKERS:
                if norm.endswith(m):
                    return None
            marker = '/plugins/'
            idx = norm.find(marker)
            if idx >= 0:
                rest = norm[idx + len(marker):]
                name = rest.split('/')[0]
                if name.endswith('.py'):
                    name = name[:-3]
                if name and name != 'base_plugin':
                    found.append((name, frame))
        frame = frame.f_back
    if not found:
        return None
    # 2) 优先归因定义了插件类的最近帧（主插件），辅助模块帧跳过
    for name, fr in found:
        if _module_defines_plugin_class(fr):
            return name
    # 3) 全栈无插件类（纯函数模块被直接调用等）→ 回退最近帧
    return found[0][0]


# ------------------------------ 授权判定 ------------------------------

def _allowed(plugin, domain, target):
    """按 capabilities 注册表判定；返回 (allowed, detail)"""
    if domain == 'filesystem:read':
        return caps_mod.check_filesystem(plugin, target, 'r')
    if domain == 'filesystem:write':
        return caps_mod.check_filesystem(plugin, target, 'w')
    if domain == 'process:exec':
        return caps_mod.check_process(plugin, None if _ANY_PROCESS else (target or None))
    if domain == 'network:tcp':
        return caps_mod.check_network(plugin, target)
    if domain == 'network:server':
        cset = caps_mod.get_capability_set(plugin)
        if cset and any(c['domain'] == 'network' and c['sub'] == 'server' for c in cset['valid']):
            return True, 'declared:network:server'
        return False, 'not-declared'
    if domain == 'database:sqlite':
        return caps_mod.check_database(plugin, target, 'sqlite')
    return True, 'unmonitored-domain'


# ------------------------------ 数据配额（v4.9.1：委托 core/quota.py，capabilities 声明模型） ------------------------------

def _in_plugin_quota_area(plugin, target):
    """target 是否落在插件配额作用目录（data/temp 自属 + filesystem:write 声明路径）。"""
    return _quota_mod._in_quota_area(plugin, target)


def _quota_usage(plugin):
    """插件配额目录总大小（字节，TTL 缓存）。"""
    return _quota_mod._quota_usage(plugin)


def _data_limit_mb(plugin=None):
    """插件配额（MB）：storage:limit 声明 > 全局默认；0 = 无限制。"""
    return _quota_mod.data_limit_mb(plugin)


def _check_data_quota(plugin, target):
    """写事件配额检查（v4.9.1 声明模型 + v4.9.2 全局总量）：落在配额作用目录且超限时 observe 记录 / enforce 拒绝。"""
    if not _quota_mod._in_quota_area(plugin, target):
        return
    # 单插件配额
    limit_mb = _quota_mod.data_limit_mb(plugin)
    if limit_mb:
        usage = _quota_mod._quota_usage(plugin)
        limit = int(limit_mb * 1048576)
        if usage >= limit:
            used = usage / 1048576
            msg = f'插件 {plugin} 数据配额超限：{used:.1f}MB / {limit_mb:.0f}MB'
            if _MODE == 'enforce':
                with _PENDING_LOCK:
                    _PENDING.append(('audit', plugin, 'blocked', msg))
                raise RuntimeError(f'运行时审计拒绝：{msg}')
            with _PENDING_LOCK:
                _PENDING.append(('audit', plugin, 'audit-warn', msg))
    # 全局总量（v4.9.2）
    g_limit = _quota_mod.total_limit_mb()
    if g_limit:
        g_usage = _quota_mod._total_usage()
        g_lim = int(g_limit * 1048576)
        if g_usage >= g_lim:
            msg = f'全部插件数据总量超限：{g_usage / 1048576:.1f}MB / {g_limit:.0f}MB'
            if _MODE == 'enforce':
                with _PENDING_LOCK:
                    _PENDING.append(('audit', plugin, 'blocked', msg))
                raise RuntimeError(f'运行时审计拒绝：{msg}')
            with _PENDING_LOCK:
                _PENDING.append(('audit', plugin, 'audit-warn', msg))


# ------------------------------ 处理 ------------------------------

def _deny(plugin, domain, target, detail):
    """未授权处理：聚合计数 + 审计 + enforce 阻断"""
    suggest = caps_mod.suggest_for_action(domain, target) or f'{domain}:{target}'
    vio = _VIOLATIONS.setdefault(plugin, {})
    item = vio.setdefault(suggest, {'count': 0, 'example': detail})
    item['count'] += 1
    item['example'] = detail
    msg = f'运行时审计：插件 {plugin} 未声明能力 {suggest}（{detail}）'
    if _MODE == 'enforce':
        with _PENDING_LOCK:
            _PENDING.append(('audit', plugin, 'blocked', msg))
        raise RuntimeError(f'运行时审计拒绝：插件 {plugin} 未声明 {suggest}（{detail}）')
    with _PENDING_LOCK:
        _PENDING.append(('audit', plugin, 'audit-warn', msg))


def _handler(event, args):
    if getattr(_local, 'in_hook', False):
        return  # 递归防护：hook 判定过程（check_* / 延迟导入）触发的嵌套事件放行
    if event not in _EVENTS:
        return
    _local.in_hook = True
    try:
        mapper = _EVENTS[event]
        try:
            domain, target = mapper(args)
        except Exception:
            return
        if not domain:
            return
        if domain == 'filesystem:read' and _is_interpreter_path(target):
            return  # Python 解释器内部文件（编码器/缓存）非插件业务
        if _is_framework_path(target):
            return  # 框架管理目录（日志/统计数据/备份），插件经框架机制写入不归因
        plugin = _locate_plugin()
        if not plugin:
            return  # 框架自身/标准库/未知来源 → 放行
        allowed, _ = _allowed(plugin, domain, target)
        if not allowed:
            _deny(plugin, domain, target, f'{event}: {target}')
            return
        if domain == 'filesystem:write':
            _check_data_quota(plugin, target)
    finally:
        _local.in_hook = False


# ------------------------------ 审计落盘（后台线程，hook 外） ------------------------------

def flush_now():
    """将待落盘审计记录立即写入 JSONL（后台线程与测试/关停共用）"""
    items = []
    with _PENDING_LOCK:
        if _PENDING:
            items, _PENDING[:] = _PENDING[:], []
    for action, plugin, result, detail in items:
        try:
            from core.audit import log_audit
            log_audit(action, plugin, result, detail)
        except Exception:
            pass  # 落盘失败不重试（避免阻塞）


def _flush_worker():
    while True:
        try:
            import time
            time.sleep(3)
            flush_now()
        except Exception:
            pass


# ------------------------------ 公共 API ------------------------------

def install_audit_hook(mode='observe'):
    """安装全局审计钩子（幂等：重复调用直接返回；mode=off 不安装）。
    由 app.py main 段在启动时调用。"""
    global _INSTALLED, _MODE, _FLUSHER
    mode = mode if mode in ('off', 'observe', 'enforce') else 'observe'
    if mode == 'off' or _INSTALLED:
        return  # 幂等：重复调用不追加钩子、不改模式（首次安装定死）
    _MODE = mode
    _INSTALLED = True
    sys.addaudithook(_handler)
    _FLUSHER = threading.Thread(target=_flush_worker, name='ftk-audit-flush',
                                daemon=True)
    _FLUSHER.start()


def get_mode():
    return _MODE


def clear_violations():
    """清空聚合表（插件重载/卸载时调用；install 前调用无副作用）"""
    _VIOLATIONS.clear()


def get_violations():
    """按插件分组返回未授权行为聚合快照（供 /api/admin/stats）：
    [{'plugin': name, 'total': n, 'details': [{'capability', 'count', 'example'}]}]"""
    out = []
    for plugin, caps in sorted(_VIOLATIONS.items()):
        details = [{'capability': c, 'count': d['count'], 'example': d['example']}
                   for c, d in sorted(caps.items())]
        out.append({'plugin': plugin, 'total': sum(d['count'] for d in details),
                    'details': details})
    return out
