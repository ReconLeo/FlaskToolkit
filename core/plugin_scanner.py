# -*- coding: utf-8 -*-
"""插件静态扫描器（v4.3.1，安全强化 P1 阶段一）

安装前对插件代码做 AST 级静态分析（后端 .py）与轻量正则分析（前端 HTML），
输出分级风险报告 + 行为范围（读写路径 / 出站网络端点）。

设计要点：
- AST 而非正则：防注释/字符串里的关键字误报，防简单混淆绕过；
- 范围提取（scope）：读写路径与网络端点清单，供阶段二 capabilities 声明交叉校验；
- 与安装链路解耦：`scan_plugin_zip` / `scan_frontend_zip` 可独立调用（CLI / 安装 API）；
- 模式由 global_var.PLUGIN_SCAN_MODE 控制：off（跳过）/ report（默认，仅报告）/ enforce（高风险拒绝安装）。

运行时审计（P1 阶段三 sys.addaudithook）不在此文件，见规划。
"""
import ast
import io
import re
import zipfile

# ------------------------------ 规则定义 ------------------------------
# 高风险 import（子进程 / 原生库 / 反序列化 / 远程执行协议）
HIGH_IMPORTS = {'subprocess', 'ctypes', 'cffi', 'pickle', 'dill', 'marshal',
                'telnetlib', 'pty', 'commands'}
# 中风险 import（网络 / 动态导入）
MEDIUM_IMPORTS = {'socket', 'ssl', 'requests', 'httpx', 'urllib3',
                  'urllib.request', 'http.client', 'ftplib', 'smtplib',
                  'asyncio.subprocess', 'importlib'}
# 低风险 import（常见但涉及文件系统/系统交互，仅记录）
LOW_IMPORTS = {'os', 'shutil', 'sys', 'pathlib', 'tempfile', 'glob'}

# 高风险调用（按"模块.函数"或裸函数名匹配）
HIGH_CALLS = {
    'subprocess.Popen': '启动子进程',
    'subprocess.run': '启动子进程',
    'subprocess.call': '启动子进程',
    'subprocess.check_output': '启动子进程',
    'subprocess.check_call': '启动子进程',
    'os.system': '执行系统命令',
    'os.popen': '执行系统命令',
    'os.execv': '替换当前进程',
    'os.execve': '替换当前进程',
    'os.spawnv': '派生进程',
    'shutil.rmtree': '递归删除目录',
    'pickle.loads': '反序列化（可构造任意代码执行）',
    'pickle.load': '反序列化（可构造任意代码执行）',
    'marshal.loads': '反序列化（可构造任意代码执行）',
    'eval': '动态执行任意代码',
    'exec': '动态执行任意代码',
    'compile': '动态编译代码',
    '__import__': '动态导入（可绕过静态检查）',
    'importlib.import_module': '动态导入（可绕过静态检查）',
    '__builtins__.eval': '动态执行任意代码',
    '__builtins__.exec': '动态执行任意代码',
}
# 中风险调用
MEDIUM_CALLS = {
    'os.remove': '删除文件',
    'os.unlink': '删除文件',
    'os.rmdir': '删除目录',
    'os.removedirs': '递归删除目录',
    'os.chmod': '修改文件权限',
    'os.chown': '修改文件属主',
    'socket.socket': '创建网络套接字',
    'requests.get': '发起 HTTP 请求',
    'requests.post': '发起 HTTP 请求',
    'requests.put': '发起 HTTP 请求',
    'requests.delete': '发起 HTTP 请求',
    'requests.request': '发起 HTTP 请求',
    'urllib.request.urlopen': '发起 HTTP 请求',
    'http.client.HTTPConnection': '发起 HTTP 请求',
    'http.client.HTTPSConnection': '发起 HTTP 请求',
}
# 网络服务端调用（监听端口）
SERVER_CALLS = {'socket.bind': '绑定网络端口（开放服务）', 'socket.listen': '监听网络端口'}

# 混淆解码调用（出现在 eval/exec 参数中即判混淆执行）
OBFUSCATE_CALLS = {'base64.b64decode', 'base64.b64decode', 'codecs.decode',
                   'zlib.decompress', 'gzip.decompress', 'bytes.fromhex', 'binascii.unhexlify'}

# 写模式字符
WRITE_MODE_CHARS = set('wax+')

_URL_RE = re.compile(r'https?://[A-Za-z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+|wss?://[A-Za-z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+')

# ------------------------------ 工具 ------------------------------

def _new_report():
    return {'findings': [], 'summary': {'high': 0, 'medium': 0, 'low': 0, 'info': 0},
            'scope': {'paths_read': [], 'paths_written': [], 'network_endpoints': []}}


def _add(report, severity, category, message, filename, line):
    report['findings'].append({
        'severity': severity, 'category': category, 'message': message,
        'file': filename, 'line': line,
    })
    report['summary'][severity] += 1


def _dedupe(report):
    """按 (severity, category, file, line) 去重，范围清单去重保序"""
    seen = set()
    findings = []
    for f in report['findings']:
        key = (f['severity'], f['category'], f['file'], f['line'], f['message'])
        if key not in seen:
            seen.add(key)
            findings.append(f)
    report['findings'] = findings
    report['summary'] = {'high': 0, 'medium': 0, 'low': 0, 'info': 0}
    for f in findings:
        report['summary'][f['severity']] += 1
    for k in ('paths_read', 'paths_written', 'network_endpoints'):
        seen_v, out = set(), []
        for v in report['scope'][k]:
            if v not in seen_v:
                seen_v.add(v)
                out.append(v)
        report['scope'][k] = out
    return report


def _merge(base, extra):
    base['findings'].extend(extra['findings'])
    for sev in base['summary']:
        base['summary'][sev] += extra['summary'][sev]
    for k in base['scope']:
        base['scope'][k].extend(extra['scope'][k])
    return base

# ------------------------------ 后端 .py 扫描（AST） ------------------------------

def _full_call_name(node, imported_aliases, instance_aliases=None):
    """取 Call 节点的完整函数名（含别名解析），返回 None 表示无法静态解析。
    instance_aliases：变量名 → 构造类名（如 s = socket.socket() → 'socket'），
    使 s.connect(...) 能归因为 socket.connect。"""
    instance_aliases = instance_aliases or {}
    def resolve(n):
        if isinstance(n, ast.Name):
            # 实例变量优先（s.connect → socket.connect）
            if n.id in instance_aliases:
                return instance_aliases[n.id]
            # 别名映射：import subprocess as sp → sp → subprocess
            return imported_aliases.get(n.id, n.id)
        if isinstance(n, ast.Attribute):
            base = resolve(n.value)
            if base:
                return f'{base}.{n.attr}'
            return None
        return None
    return resolve(node.func)


def _import_context(tree):
    """收集 import 别名映射（含 from-import 的成员级映射）"""
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                aliases[a.asname or a.name.split('.')[0]] = a.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for a in node.names:
                aliases[a.asname or a.name] = node.module
    return aliases


def _str_value(node):
    """尝试静态求值字符串常量（含 f-string 的静态部分拼接结果为 None）"""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_write_mode(mode_str):
    if not mode_str:
        return False
    return any(c in WRITE_MODE_CHARS for c in mode_str)


def scan_code(code: str, filename: str = '<code>') -> dict:
    """扫描一段 Python 源码，返回风险报告"""
    report = _new_report()
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        _add(report, 'high', 'syntax', f'源码无法解析（可能混淆/加密）：{e}', filename, e.lineno or 0)
        return report

    aliases = _import_context(tree)

    # 实例别名追踪：x = socket.socket() → x.connect/bind 可归因到 socket
    instance_aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            cname = _full_call_name(node.value, aliases)
            if cname and cname.startswith('socket.socket'):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        instance_aliases[t.id] = 'socket'

    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imported_modules.add(a.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split('.')[0])

    for mod in sorted(imported_modules):
        if mod in HIGH_IMPORTS:
            _add(report, 'high', 'import', f'导入高风险模块 {mod}', filename, 0)
        elif mod in MEDIUM_IMPORTS:
            _add(report, 'medium', 'import', f'导入网络/动态加载模块 {mod}', filename, 0)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _full_call_name(node, aliases, instance_aliases)
        if not name:
            continue
        line = getattr(node, 'lineno', 0)

        # open()：模式 + 路径范围提取
        if name in ('open', 'io.open', 'builtins.open'):
            mode = None
            if len(node.args) >= 2:
                mode = _str_value(node.args[1])
            elif node.keywords:
                for kw in node.keywords:
                    if kw.arg == 'mode':
                        mode = _str_value(kw.value)
            path = _str_value(node.args[0]) if node.args else None
            if _is_write_mode(mode):
                _add(report, 'medium', 'file-write', '文件写入（open 写模式）', filename, line)
                if path:
                    report['scope']['paths_written'].append(path)
            else:
                _add(report, 'info', 'file-read', '文件读取（open）', filename, line)
                if path:
                    report['scope']['paths_read'].append(path)
            continue

        # 网络端点提取：requests/urllib 调用的 URL 字面量；socket.connect 的 host
        if name in ('requests.get', 'requests.post', 'requests.put', 'requests.delete',
                    'requests.request', 'urllib.request.urlopen'):
            url = _str_value(node.args[0]) if node.args else None
            if url and _URL_RE.search(url):
                report['scope']['network_endpoints'].append(url)
        if name == 'socket.connect' and node.args:
            arg = node.args[0]
            # connect(('host', port))
            if isinstance(arg, ast.Tuple) and len(arg.elts) == 2:
                host = _str_value(arg.elts[0])
                if host:
                    report['scope']['network_endpoints'].append(f'tcp://{host}')
            else:
                host = _str_value(arg)
                if host:
                    report['scope']['network_endpoints'].append(f'tcp://{host}')

        # 网络服务端
        if name in SERVER_CALLS:
            _add(report, 'high', 'network-server', SERVER_CALLS[name], filename, line)
            continue

        # 混淆执行：eval/exec 的参数里出现解码调用
        if name in ('eval', 'exec', 'compile'):
            _add(report, 'high', 'dynamic-exec', HIGH_CALLS[name], filename, line)
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    sub_name = _full_call_name(sub, aliases, instance_aliases)
                    if sub_name in OBFUSCATE_CALLS:
                        _add(report, 'high', 'obfuscation',
                             f'动态执行解码数据（{sub_name} → {name}，疑似混淆）', filename, line)
            continue

        if name in ('__import__', 'importlib.import_module'):
            _add(report, 'high', 'dynamic-import', HIGH_CALLS[name], filename, line)
            # 参数非常量 → 额外混淆告警
            if node.args and _str_value(node.args[0]) is None:
                _add(report, 'high', 'obfuscation', '动态导入参数为非常量（拼接/解码构造）', filename, line)
            continue

        if name in HIGH_CALLS:
            _add(report, 'high', HIGH_CALLS[name].split('（')[0] if '（' in HIGH_CALLS[name] else 'dangerous-call',
                 HIGH_CALLS[name], filename, line)
            continue

        if name in MEDIUM_CALLS:
            _add(report, 'medium', 'dangerous-call', MEDIUM_CALLS[name], filename, line)

    # 全量字符串常量中的 URL（网络范围兜底提取）
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for m in _URL_RE.findall(node.value):
                report['scope']['network_endpoints'].append(m)

    return _dedupe(report)


def scan_file(path: str) -> dict:
    """扫描单个 .py 文件"""
    with io.open(path, 'r', encoding='utf-8', errors='replace') as f:
        return scan_code(f.read(), filename=path.replace('\\', '/').split('/')[-1])

# ------------------------------ 插件包（.zip）扫描 ------------------------------

def scan_plugin_zip(zip_path: str) -> dict:
    """扫描后端插件包内全部 .py 成员（跳过 templates/ static/ __pycache__）"""
    report = _new_report()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            if not member.endswith('.py'):
                continue
            if any(seg in member for seg in ('__pycache__', 'templates/', 'static/')):
                continue
            try:
                code = zf.read(member).decode('utf-8', errors='replace')
            except Exception:
                continue
            sub = scan_code(code, filename=member)
            _merge(report, sub)
    return _dedupe(report)

# ------------------------------ 前端工具（HTML/JS）轻量扫描 ------------------------------

_FE_PATTERNS = [
    ('high', 'dynamic-exec', re.compile(r'\beval\s*\(|new\s+Function\s*\('), '动态执行代码（eval/new Function）'),
    ('medium', 'external-script', re.compile(r'<script[^>]+src=["\'](https?://[^"\']+)["\']', re.I), '引用外部脚本'),
    ('medium', 'external-network', re.compile(r'''(?:fetch|XMLHttpRequest|\.open|sendBeacon|WebSocket)\s*\(?\s*["'`](https?://[^"'`]+)["'`]'''), '访问外部网络地址'),
    ('low', 'cookie-access', re.compile(r'document\.cookie'), '读取 Cookie'),
    ('low', 'storage-access', re.compile(r'localStorage|sessionStorage'), '访问本地存储'),
]


def scan_frontend_html(html: str, filename: str = '<html>') -> dict:
    """前端工具页轻量扫描（正则级，覆盖外链/动态执行/Cookie 与本地存储访问）"""
    report = _new_report()
    lines = html.split('\n')
    for severity, category, pattern, message in _FE_PATTERNS:
        for i, line in enumerate(lines, 1):
            m = pattern.search(line)
            if m:
                _add(report, severity, category, message, filename, i)
                # 范围提取：捕获组里的 URL
                for g in m.groups():
                    if g and _URL_RE.search(g):
                        report['scope']['network_endpoints'].append(g)
    return _dedupe(report)


def scan_frontend_zip(zip_path: str) -> dict:
    """扫描前端工具包内全部 .html 成员"""
    report = _new_report()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            if not member.lower().endswith('.html'):
                continue
            html = zf.read(member).decode('utf-8', errors='replace')
            _merge(report, scan_frontend_html(html, filename=member))
    return _dedupe(report)

# ------------------------------ 决策辅助 ------------------------------

def should_block(report: dict) -> bool:
    """enforce 模式决策：存在任一高风险即阻断"""
    return report['summary']['high'] > 0


def format_report(report: dict, title: str = '静态扫描报告') -> str:
    """人类可读报告（CLI / 日志用）"""
    s = report['summary']
    lines = [f'==== {title}：high={s["high"]} medium={s["medium"]} low={s["low"]} info={s["info"]} ====']
    for f in report['findings']:
        lines.append(f'[{f["severity"].upper():<6}] {f["file"]}:{f["line"]} {f["category"]} — {f["message"]}')
    scope = report['scope']
    if scope['paths_written'] or scope['paths_read']:
        lines.append(f'范围-路径: 写 {scope["paths_written"]} / 读 {scope["paths_read"]}')
    if scope['network_endpoints']:
        lines.append(f'范围-网络: {scope["network_endpoints"]}')
    return '\n'.join(lines)
