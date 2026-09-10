# -*- coding: utf-8 -*-
"""core/plugin_deps.py — 插件依赖解析（v4.16 规划）

提供：
- 依赖规格解析 ``parse_dep_spec``：``dependencies``/``pip_dependencies`` 支持
  ``name`` / ``name>=1.2`` / ``name<2`` / ``name==1.2`` / ``name>=1,<2``（逗号多约束）。
- 纯 stdlib 版本比较 ``version_satisfies`` / ``_version_tuple``（不引入 packaging）。
- 依赖图拓扑排序 + 循环检测 ``resolve_dependency_order``（Kahn 算法，确定性输出）。

拓扑排序只认插件名；版本约束仅做存在性+满足性校验（由调用方结合目标插件/pip 包版本判断）。
"""
import heapq
import re

__all__ = ['parse_dep_spec', 'dep_name', 'version_satisfies',
           'resolve_dependency_order', '_version_tuple']

_OPS = ('>=', '<=', '==', '!=', '>', '<')
# 预发布标记权重（越小越"早期"），正式版 weight=0
_PR_WEIGHTS = {'a': -3, 'alpha': -3, 'b': -2, 'beta': -2,
               'rc': -1, 'pre': -1, 'preview': -1}


def dep_name(spec: str) -> str:
    """从依赖规格中提取裸名（不带动词约束）。如 'auth>=1.0' -> 'auth'。"""
    return parse_dep_spec(spec)[0]


def parse_dep_spec(spec):
    """解析依赖规格 -> (name, [(op, ver), ...])。

    例：'auth>=1.0,<2' -> ('auth', [('>=', '1.0'), ('<', '2')])
    """
    spec = (spec or '').strip()
    if not spec:
        return ('', [])
    i = 0
    while i < len(spec) and (spec[i].isalnum() or spec[i] in '_.-'):
        i += 1
    name = spec[:i]
    rest = spec[i:].strip()
    constraints = []
    if rest:
        for part in rest.split(','):
            part = part.strip()
            if not part:
                continue
            m = re.match(r'^\s*([<>=!]+)\s*([0-9][^\s,]*)\s*$', part)
            if not m:
                raise ValueError(f'无效版本约束: "{part}"（支持 >=,>,<,<=,==,!=，如 auth>=1.0）')
            op, ver = m.group(1), m.group(2)
            if op not in _OPS:
                raise ValueError(f'不支持的版本运算符: "{op}"')
            constraints.append((op, ver))
    return (name, constraints)


def _version_tuple(v):
    """把版本串转成可比较元组 (major, minor, patch, prerelease_weight, prerelease_num)。

    纯 stdlib 简化语义版本比较：'1.2.3' > '1.2.3rc1' > '1.2.3b1' > '1.2.3a1'。
    """
    v = str(v or '').strip().lower()
    m = re.match(r'^(\d+)(?:\.(\d+))?(?:\.(\d+))?', v)
    if not m:
        return (0, 0, 0, 0, 0)
    major = int(m.group(1))
    minor = int(m.group(2) or 0)
    patch = int(m.group(3) or 0)
    rest = v[m.end():]
    weight, num = 0, 0
    if rest:
        pm = re.match(r'^([a-z]+)(\d*)', rest)
        if pm:
            weight = _PR_WEIGHTS.get(pm.group(1), -10)
            num = int(pm.group(2) or 0)
    return (major, minor, patch, weight, num)


def _compare(iv, op, rv):
    if op == '>=':
        return iv >= rv
    if op == '>':
        return iv > rv
    if op == '<':
        return iv < rv
    if op == '<=':
        return iv <= rv
    if op == '==':
        return iv == rv
    if op == '!=':
        return iv != rv
    return False


def version_satisfies(installed_version, constraints):
    """已装版本是否满足全部约束。installed_version 为 None/空视为不满足。"""
    if not constraints:
        return True
    if not installed_version:
        return False
    iv = _version_tuple(installed_version)
    for op, ver in constraints:
        if not _compare(iv, op, _version_tuple(ver)):
            return False
    return True


def resolve_dependency_order(plugins):
    """依赖图拓扑排序 + 循环检测（Kahn 算法，确定性按名序出队）。

    :param plugins: ``{plugin_name: set(dependency_names)}``（仅插件名，缺失依赖由调用方预滤）。
    :return: ``(topo_order, cycles)``
        - topo_order: 满足依赖先行的加载顺序列表
        - cycles: 循环依赖组列表（每组为一个环路径 [a,b,a]）
    """
    nodes = set(plugins)
    deps = {n: set(d for d in plugins[n] if d in nodes) for n in plugins}

    indeg = {n: len(deps[n]) for n in nodes}
    rev = {n: set() for n in nodes}
    for n, ds in deps.items():
        for d in ds:
            rev[d].add(n)

    heap = [n for n in nodes if indeg[n] == 0]
    heapq.heapify(heap)
    order = []
    while heap:
        n = heapq.heappop(heap)
        order.append(n)
        for m in sorted(rev[n]):
            indeg[m] -= 1
            if indeg[m] == 0:
                heapq.heappush(heap, m)

    remaining = [n for n in nodes if indeg[n] > 0]
    cycles = _find_cycles(remaining, deps)
    return order, cycles


def _find_cycles(nodes, deps):
    """从 Kahn 剩余节点中划分互斥环组。"""
    if not nodes:
        return []
    cycles = []
    visited = set()

    def walk(cur, path, pos):
        if cur in pos:
            return path[pos[cur]:] + [cur]
        if cur in visited:
            return None
        pos[cur] = len(path)
        path.append(cur)
        for nxt in sorted(deps.get(cur, ())):
            if nxt in nodes:
                r = walk(nxt, path, pos)
                if r:
                    return r
        path.pop()
        pos.pop(cur, None)
        return None

    for n in sorted(nodes):
        if n not in visited:
            r = walk(n, [], {})
            if r:
                cycles.append(r)
                visited.update(r)
    return cycles
