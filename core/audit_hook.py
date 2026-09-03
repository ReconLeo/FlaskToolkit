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

from core import capabilities as caps_mod

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


def _is_interpreter_path(path):
    """Python 解释器内部路径（stdlib/site-packages/编码器缓存）——插件业务无关，跳过"""
    norm = _norm_slash(os.path.abspath(str(path)))
    return norm.startswith(_SYS_PREFIX) or '/__pycache__/' in norm


def _locate_plugin():
    """遍历调用栈，定位 plugins/<name>.py 最近帧的插件名。
    base_plugin（框架内置）不视为插件来源；无插件帧返回 None（放行）。"""
    found = None
    frame = sys._getframe(1)
    while frame is not None:
        fname = frame.f_globals.get('__file__')
        if fname:
            norm = _norm_slash(fname)
            marker = '/plugins/'
            idx = norm.find(marker)
            if idx >= 0:
                rest = norm[idx + len(marker):]
                name = rest.split('/')[0]
                if name.endswith('.py'):
                    name = name[:-3]
                if name and name != 'base_plugin':
                    found = name
                    break  # 最近调用者优先
        frame = frame.f_back
    return found


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
        plugin = _locate_plugin()
        if not plugin:
            return  # 框架自身/标准库/未知来源 → 放行
        allowed, _ = _allowed(plugin, domain, target)
        if not allowed:
            _deny(plugin, domain, target, f'{event}: {target}')
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
