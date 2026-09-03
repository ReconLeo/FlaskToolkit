# -*- coding: utf-8 -*-
"""插件能力声明（capabilities）模型（v4.3.2，安全强化 P1 阶段二）

插件在 plugin.json 中以可选字段 `capabilities` 声明白名单授权，安装时与
静态扫描器（core/plugin_scanner.py）的行为范围输出交叉校验，产出 mismatch 清单；
解析结果注册进内存注册表，作为阶段三（4.4.0）运行时审计钩子的授权判定依据。

设计要点：
- Deny by Default：未声明即未授权（fail-closed）；
- 自属路径隐式豁免（implicit grants）：插件自己的 configs/data/temp 无需声明；
- 开放能力目录：未知域安装时告警但不拒绝，运行时不产生授权；
- 校验层（安装时）与运行时层（check_*）共用同一套匹配语义，拼接写法的扫描
  盲区由运行时层兜底。

能力语法（域:子域:参数，无参项允许单段）：
    filesystem:read:<path>       路径前缀匹配（目录级授权，含子内容；尾部 * 等价目录）
    filesystem:write:<path>      同上
    network:http:<scheme://host[:port][/path*]>   host 精确或 *.domain 子域通配（禁裸 *）
    network:tcp:<host[:port]>    / network:udp:<host[:port]>（无端口=任意端口）
    network:server:<host:port>   插件监听端口（bind/listen）
    webhook:<platform>:<url-pattern>  平台枚举（wecom/dingtalk/feishu）+ URL 白名单，
                                      URL 语义同 network:http（可兼作 HTTP 出站授权）
    process:exec[.<bin>]         子进程（带 bin=仅该可执行名；运行时比对）
    scheduler                    定时任务
    database:sqlite:<path>       / database:mysql:<host:port/db> / database:postgres:...
    device:serial:<port>         / device:print
    env:read:<pattern>           环境变量名前缀/通配
"""
import json
import os
import re
import zipfile

# ------------------------------ 能力目录 ------------------------------

KNOWN_DOMAINS = {'filesystem', 'network', 'webhook', 'process', 'scheduler',
                 'database', 'device', 'env'}
WEBHOOK_PLATFORMS = {'wecom', 'dingtalk', 'feishu'}

# 安装时可从扫描事实交叉验证的域（其余域仅记录声明，不做 mismatch 判定）
_VERIFIABLE_DOMAINS = {'filesystem', 'network', 'webhook', 'process'}

_DB_IMPORTS = {'sqlite3': 'database:sqlite', 'pymysql': 'database:mysql',
               'psycopg2': 'database:postgres'}
_DEVICE_IMPORTS = {'serial': 'device:serial'}


# ------------------------------ 路径匹配 ------------------------------

def _norm_path(p):
    """归一化路径：normcase（Windows 小写+统一分隔符）→ normpath → 正斜杠"""
    return os.path.normpath(os.path.normcase(str(p))).replace('\\', '/')


def _strip_glob(pattern):
    p = pattern.rstrip('/')
    if p.endswith('/*'):
        p = p[:-2]
    elif p.endswith('*'):
        p = p[:-1]
    return p


def match_path_decl(decl_param, path):
    """声明路径（目录级前缀授权）是否覆盖 path：相等或为父目录。
    data / data/ / data/* 三种写法等价（均覆盖 data/ 下任意深度）。"""
    d = _strip_glob(_norm_path(decl_param))
    p = _norm_path(path)
    if not d:
        return False
    return p == d or p.startswith(d + '/')


def _rel_to_base(path, base_dir):
    """绝对路径若位于 base_dir 下则转为相对（便于与相对声明比较）"""
    p = _norm_path(path)
    b = _norm_path(base_dir)
    if p.startswith(b + '/'):
        return p[len(b) + 1:]
    return p


def is_implicit_grant(plugin_name, path, base_dir=None):
    """自属路径隐式豁免（v4.3.2 决策定稿）：
    - plugins/configs/<name>.json（基类 load_config/save_config）
    - plugins/data/<name>/**（插件专属数据目录）
    - plugins/temp/<name>/**（插件临时目录）
    相对/绝对路径均可判定；跨插件目录不豁免。"""
    import global_var
    base = base_dir or global_var.BASE_DIR
    p = _rel_to_base(path, base)
    name = str(plugin_name).lower()
    if p == f'plugins/configs/{name}.json':
        return True
    for seg in ('data', 'temp'):
        if p == f'plugins/{seg}/{name}' or p.startswith(f'plugins/{seg}/{name}/'):
            return True
    return False


# ------------------------------ URL / 主机匹配 ------------------------------

_EP_RE = re.compile(r'^(https?|wss?|tcp|udp)://([^/:]+|\*\.[^/:]+)(?::(\d+))?(/.*)?$')


def parse_endpoint(endpoint):
    """解析端点/URL 声明 → {'scheme','host','port','path'} | None（非法）"""
    m = _EP_RE.match(endpoint.strip())
    if not m:
        return None
    scheme, host, port, path = m.group(1), m.group(2).lower(), m.group(3), m.group(4)
    if host == '*' or not host:
        return None  # 禁止裸 * host
    return {'scheme': scheme, 'host': host, 'port': port, 'path': path or ''}


def _host_match(decl_host, host):
    if decl_host.startswith('*.'):
        return host.endswith(decl_host[1:])  # *.corp.local 匹配 erp.corp.local
    return decl_host == host


def _default_port(scheme):
    return {'https': '443', 'wss': '443', 'http': '80', 'ws': '80'}.get(scheme)


def match_url_decl(decl_param, endpoint):
    """network:http / webhook 的 URL 声明是否覆盖 endpoint。
    端口：声明带端口则须精确（端点缺省按 scheme 默认端口折算）；声明不带=任意端口。
    路径：声明带 path 为前缀匹配（尾 * 递归）；不带 = 整站。"""
    d, e = parse_endpoint(decl_param), parse_endpoint(endpoint)
    if not d or not e:
        return False
    if d['scheme'] != e['scheme']:
        return False
    if not _host_match(d['host'], e['host']):
        return False
    if d['port']:
        ep_port = e['port'] or _default_port(e['scheme'])
        if ep_port != d['port']:
            return False
    dp = d['path'].rstrip('*').rstrip('/')
    if dp == '':
        return True
    ep = (e['path'] or '/').split('?')[0]
    return ep == dp or ep.startswith(dp + '/') or ep.startswith(dp)


def match_tcp_decl(decl_param, endpoint, proto='tcp'):
    """network:tcp/udp 声明（host[:port]）是否覆盖 endpoint（tcp://host[:port]）。"""
    d = parse_endpoint(f'{proto}://{decl_param.strip()}')
    e = parse_endpoint(endpoint)
    if not d or not e or e['scheme'] != proto:
        return False
    if d['host'] != e['host']:
        return False
    if d['port'] and d['port'] != e['port']:
        return False
    return True


def match_env_decl(decl_param, var_name):
    """env:read 声明（变量名前缀或 * 通配）是否覆盖 var_name"""
    pat = decl_param.strip()
    if pat.endswith('*'):
        return var_name.startswith(pat[:-1])
    return var_name.startswith(pat)


# ------------------------------ 声明解析 ------------------------------

def parse_capabilities(caps):
    """解析 capabilities 列表 → {'valid': [cap], 'errors': [...], 'unknown': [...]}
    cap = {'domain','sub','param','raw'}；语法非法项进 errors（fail-closed 该条不生效）；
    未知域进 unknown（告警不拒绝，运行时不产生授权）。"""
    out = {'valid': [], 'errors': [], 'unknown': []}
    if not caps:
        return out
    if not isinstance(caps, list):
        out['errors'].append({'raw': repr(caps), 'reason': 'capabilities 须为字符串列表'})
        return out
    for raw in caps:
        if not isinstance(raw, str) or not raw.strip():
            out['errors'].append({'raw': repr(raw), 'reason': '声明须为非空字符串'})
            continue
        parts = raw.strip().split(':')
        cap = {'domain': parts[0], 'sub': parts[1] if len(parts) > 1 else '',
               'param': ':'.join(parts[2:]) if len(parts) > 2 else '', 'raw': raw.strip()}
        dom, sub, param = cap['domain'], cap['sub'], cap['param']
        # 语法校验
        if dom not in KNOWN_DOMAINS:
            out['unknown'].append({'raw': raw.strip(),
                                   'reason': f'未知能力域 {dom}（安装告警，运行时不产生授权）'})
            continue
        ok = True
        reason = ''
        if dom == 'filesystem':
            ok = sub in ('read', 'write') and bool(param)
            reason = '须为 filesystem:read|write:<路径>'
        elif dom == 'network':
            ok = sub in ('http', 'tcp', 'udp', 'server') and bool(param)
            reason = '须为 network:http|tcp|udp|server:<端点>'
            if ok and sub == 'http' and parse_endpoint(param) is None:
                ok, reason = False, 'URL 非法或使用了裸 * 主机（至少保留一级域）'
            if ok and sub in ('tcp', 'udp') and parse_endpoint(f'{sub}://{param}') is None:
                ok, reason = False, f'{sub} 端点非法（host[:port]）'
        elif dom == 'webhook':
            ok = sub in WEBHOOK_PLATFORMS and bool(param) and parse_endpoint(param) is not None
            reason = f'须为 webhook:{ "|".join(sorted(WEBHOOK_PLATFORMS)) }:<URL>'
        elif dom == 'process':
            ok = sub == 'exec'  # process:exec 或 process:exec:<bin>（param 为可执行名）
            reason = '须为 process:exec 或 process:exec:<可执行名>'
        elif dom == 'scheduler':
            ok = not sub and not param
            reason = 'scheduler 无参数'
        elif dom == 'database':
            ok = sub in ('sqlite', 'mysql', 'postgres') and bool(param)
            reason = '须为 database:sqlite|mysql|postgres:<目标>'
        elif dom == 'device':
            ok = (sub == 'print' and not param) or (sub == 'serial' and bool(param))
            reason = '须为 device:print 或 device:serial:<端口>'
        elif dom == 'env':
            ok = sub == 'read' and bool(param)
            reason = '须为 env:read:<变量名模式>'
        if ok:
            out['valid'].append(cap)
        else:
            out['errors'].append({'raw': raw.strip(), 'reason': reason})
    return out


# ------------------------------ 安装链路交叉校验 ------------------------------

def _suggest_fs(kind, path):
    """文件路径 → 目录级建议声明（归一到父目录，保留原样大小写便于作者回填）"""
    p = str(path).replace('\\', '/')
    parent = p if p.endswith('/') else (p.rsplit('/', 1)[0] if '/' in p else p)
    return f'filesystem:{kind}:{parent}/'


def _suggest_endpoint(endpoint):
    e = parse_endpoint(endpoint)
    if not e:
        return None
    if e['scheme'] in ('http', 'https', 'ws', 'wss'):
        port = f':{e["port"]}' if e['port'] and e['port'] != _default_port(e['scheme']) else ''
        return f'network:http:{e["scheme"]}://{e["host"]}{port}/'
    return f'network:{e["scheme"]}:{e["host"]}'


def _has_fs_grant(valid, kind, path):
    return any(c['domain'] == 'filesystem' and c['sub'] == kind and match_path_decl(c['param'], path)
               for c in valid)


def cross_validate(plugin_name, scan_report, capabilities, base_dir=None):
    """安装链路交叉校验：扫描事实（scope/findings）× 声明白名单 → mismatch 清单。

    返回 {
      'declared': [...], 'errors': [...], 'unknown': [...],
      'missing': [...],          # 检出但未声明（且未命中隐式豁免）→ enforce 拒绝依据
      'implicit_granted': [...], # 命中自属路径豁免的检出（透明展示）
      'unused': [...],           # 声明了但未检出使用（info 提示，不阻断）
      'suggested': [...],        # 建议声明（可整段复制回 plugin.json）
      'ok': bool                 # enforce 门禁判定：missing 为空
    }"""
    import global_var
    base = base_dir or global_var.BASE_DIR
    parsed = parse_capabilities(capabilities or [])
    valid = parsed['valid']
    res = {
        'declared': [c['raw'] for c in valid],
        'errors': parsed['errors'],
        'unknown': parsed['unknown'],
        'missing': [], 'implicit_granted': [], 'unused': [], 'suggested': [],
    }
    used_raw = set()
    report = scan_report or {}
    scope = report.get('scope') or {'paths_read': [], 'paths_written': [], 'network_endpoints': []}
    findings = report.get('findings') or []

    # 1. 文件读写路径
    for kind, key in (('write', 'paths_written'), ('read', 'paths_read')):
        for p in scope.get(key, []):
            if is_implicit_grant(plugin_name, p, base):
                res['implicit_granted'].append(f'{kind}:{p}')
                continue
            hit = [c for c in valid if c['domain'] == 'filesystem' and c['sub'] == kind
                   and match_path_decl(c['param'], p)]
            if hit:
                used_raw.update(c['raw'] for c in hit)
            else:
                res['missing'].append(f'filesystem:{kind}:{p}')

    # 2. 网络端点
    for ep in scope.get('network_endpoints', []):
        e = parse_endpoint(ep)
        if not e:
            continue
        if e['scheme'] in ('http', 'https', 'ws', 'wss'):
            hit = [c for c in valid
                   if (c['domain'] == 'network' and c['sub'] == 'http'
                       and match_url_decl(c['param'], ep))
                   or (c['domain'] == 'webhook' and match_url_decl(c['param'], ep))]
            if hit:
                used_raw.update(c['raw'] for c in hit)
            else:
                res['missing'].append(f'network:http:{ep}')
        elif e['scheme'] in ('tcp', 'udp'):
            hit = [c for c in valid if c['domain'] == 'network' and c['sub'] == e['scheme']
                   and match_tcp_decl(c['param'], ep, e['scheme'])]
            if hit:
                used_raw.update(c['raw'] for c in hit)
            else:
                res['missing'].append(f'network:{e["scheme"]}:{e["host"]}')

    # 3. 子进程 / 网络服务端 / 数据库 / 设备（按 findings 类别）
    f_msgs = [f.get('message', '') for f in findings]
    f_cats = [f.get('category', '') for f in findings]
    if (any('subprocess' in m for m in f_msgs)
            or any('子进程' in m or '系统命令' in m for m in f_msgs)):
        hit = [c for c in valid if c['domain'] == 'process']
        if hit:
            used_raw.update(c['raw'] for c in hit)
        else:
            res['missing'].append('process:exec')
    if 'network-server' in f_cats:
        hit = [c for c in valid if c['domain'] == 'network' and c['sub'] == 'server']
        if hit:
            used_raw.update(c['raw'] for c in hit)
        else:
            res['missing'].append('network:server:<host:port>')
    for mod, cap_prefix in {**_DB_IMPORTS, **_DEVICE_IMPORTS}.items():
        if any(f'模块 {mod}' in m for m in f_msgs):
            hit = [c for c in valid if c['raw'].startswith(cap_prefix)]
            if not hit:
                res['missing'].append(f'{cap_prefix}:<目标>')

    # 4. 声明未使用（仅对可静态验证的域；process/server 细粒度无法完全判定，不提示）
    for c in valid:
        if c['domain'] in ('filesystem', 'network', 'webhook') and c['raw'] not in used_raw:
            res['unused'].append(c['raw'])

    # 5. 建议声明（missing → 目录/主机归一，去重保序）
    for m in res['missing']:
        if m.startswith('filesystem:'):
            parts = m.split(':', 2)
            sug = _suggest_fs(parts[1], parts[2])
        elif m.startswith('network:http:'):
            sug = _suggest_endpoint(m.split(':', 2)[2])
        elif m.startswith(('network:tcp:', 'network:udp:')):
            sug = m  # host 已归一，即建议
        elif m == 'process:exec':
            sug = 'process:exec'
        elif m.startswith('network:server'):
            sug = 'network:server:0.0.0.0:<port>'
        elif m.startswith(('database:', 'device:')):
            sug = m  # 带占位提示，由作者补具体目标
        else:
            sug = None
        if sug and sug not in res['suggested']:
            res['suggested'].append(sug)

    res['ok'] = not res['missing']
    return res


def read_pack_capabilities(zip_path):
    """读取插件包（.zip）内 plugin.json 的 capabilities 字段（无则 None）"""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            if 'plugin.json' not in zf.namelist():
                return None
            desc = json.loads(zf.read('plugin.json').decode('utf-8'))
            return desc.get('capabilities')
    except Exception:
        return None


# ------------------------------ 运行时注册表（阶段三授权基准） ------------------------------

_REGISTRY = {}


def register_capabilities(plugin_name, caps):
    """注册插件能力集（插件加载时调用；caps 为声明列表或 None）"""
    _REGISTRY[str(plugin_name)] = parse_capabilities(caps or [])


def unregister_capabilities(plugin_name):
    _REGISTRY.pop(str(plugin_name), None)


def clear_capabilities():
    """清空注册表（load_plugins 重载前调用，按现存插件重建）"""
    _REGISTRY.clear()


def get_capability_set(plugin_name):
    return _REGISTRY.get(str(plugin_name))


def load_capabilities_from_desc(desc_path):
    """从插件描述文件（plugins/<name>.json）读取 capabilities 字段"""
    try:
        with open(desc_path, 'r', encoding='utf-8') as f:
            desc = json.load(f)
        return desc.get('capabilities')
    except Exception:
        return None


def check_filesystem(plugin_name, path, mode='r', base_dir=None):
    """运行时授权判定（阶段三审计钩子契约）：返回 (allowed, reason)。
    先判自属路径隐式豁免，再查声明白名单；未注册/未声明 → 拒绝（fail-closed）。"""
    if is_implicit_grant(plugin_name, path, base_dir):
        return True, 'implicit-grant'
    caps = _REGISTRY.get(str(plugin_name))
    if not caps:
        return False, 'no-capability-set'
    kind = 'write' if any(c in (mode or 'r') for c in 'wax+') else 'read'
    for c in caps['valid']:
        if c['domain'] == 'filesystem' and c['sub'] == kind and match_path_decl(c['param'], path):
            return True, f'declared:{c["raw"]}'
    return False, 'not-declared'


def check_network(plugin_name, endpoint):
    """运行时网络授权判定（阶段三"防火墙"规则）：endpoint 支持
    http(s)://host[:port][/path] 与 tcp://host[:port] / udp://..."""
    caps = _REGISTRY.get(str(plugin_name))
    if not caps:
        return False, 'no-capability-set'
    e = parse_endpoint(endpoint)
    if not e:
        return False, 'invalid-endpoint'
    for c in caps['valid']:
        if c['domain'] == 'network' and c['sub'] == 'http' and e['scheme'] in ('http', 'https', 'ws', 'wss'):
            if match_url_decl(c['param'], endpoint):
                return True, f'declared:{c["raw"]}'
        elif c['domain'] == 'webhook' and e['scheme'] in ('http', 'https'):
            if match_url_decl(c['param'], endpoint):
                return True, f'declared:{c["raw"]}'
        elif c['domain'] == 'network' and c['sub'] in ('tcp', 'udp') and e['scheme'] == c['sub']:
            if match_tcp_decl(c['param'], endpoint, c['sub']):
                return True, f'declared:{c["raw"]}'
    return False, 'not-declared'


def check_process(plugin_name, bin_name=None):
    """运行时子进程授权判定；带 bin 的声明仅在可执行名匹配时授权"""
    caps = _REGISTRY.get(str(plugin_name))
    if not caps:
        return False, 'no-capability-set'
    for c in caps['valid']:
        if c['domain'] != 'process':
            continue
        if not c['param']:  # process:exec —— 任意子进程
            return True, 'declared:process:exec'
        if bin_name and (c['param'] == bin_name or c['param'].endswith('/' + bin_name)
                         or c['param'].endswith('\\' + bin_name)):
            return True, f'declared:{c["raw"]}'
    return False, 'not-declared'
