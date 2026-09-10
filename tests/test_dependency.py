# -*- coding: utf-8 -*-
"""test_dependency.py — core/plugin_deps.py 依赖解析单元测试

覆盖：parse_dep_spec 各形态、版本比较（含预发布）、version_satisfies、
resolve_dependency_order 拓扑序/环检测。

可直接 `python tests/test_dependency.py` 运行。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.plugin_deps import (parse_dep_spec, dep_name, version_satisfies,
                              resolve_dependency_order, _version_tuple)


def test_parse_bare():
    assert parse_dep_spec('auth') == ('auth', []), parse_dep_spec('auth')
    assert parse_dep_spec('  kaleido_crypto ') == ('kaleido_crypto', [])


def test_parse_single_constraint():
    assert parse_dep_spec('auth>=1.2') == ('auth', [('>=', '1.2')])
    assert parse_dep_spec('requests>=2,<3') == ('requests', [('>=', '2'), ('<', '3')])
    assert parse_dep_spec('pkg==1.2.3') == ('pkg', [('==', '1.2.3')])
    assert parse_dep_spec('pkg!=1.0') == ('pkg', [('!=', '1.0')])


def test_dep_name():
    assert dep_name('auth>=1.0') == 'auth'
    assert dep_name('requests') == 'requests'


def test_parse_invalid():
    try:
        parse_dep_spec('auth>=>1.0')
        assert False, '应抛错'
    except ValueError:
        pass


def test_version_tuple_order():
    assert _version_tuple('1.0.0') > _version_tuple('0.9.9')
    assert _version_tuple('1.2.3') > _version_tuple('1.2.3rc1')
    assert _version_tuple('1.2.3rc1') > _version_tuple('1.2.3b1')
    assert _version_tuple('1.2.3b1') > _version_tuple('1.2.3a1')
    assert _version_tuple('1.2') == _version_tuple('1.2.0')


def test_version_satisfies():
    assert version_satisfies('1.5', [('>=', '1.0')])
    assert not version_satisfies('0.9', [('>=', '1.0')])
    assert version_satisfies('1.5', [('>=', '1.0'), ('<', '2.0')])
    assert not version_satisfies('2.1', [('>=', '1.0'), ('<', '2.0')])
    assert version_satisfies('1.2.3', [('==', '1.2.3')])
    assert not version_satisfies('1.2.4', [('==', '1.2.3')])
    assert version_satisfies('1.2.4', [('!=', '1.2.3')])
    assert not version_satisfies('2.0.0b1', [('>=', '2.0.0')])  # 预发布 < 正式
    assert version_satisfies(None, [])  # 无约束恒真


def test_topo_simple():
    plugins = {'auth': set(), 'um': {'auth'}, 'k': {'um'}}
    order, cycles = resolve_dependency_order(plugins)
    assert cycles == [], cycles
    assert order.index('auth') < order.index('um') < order.index('k'), order


def test_topo_multiple_roots():
    plugins = {'a': set(), 'b': set(), 'c': {'a', 'b'}}
    order, cycles = resolve_dependency_order(plugins)
    assert cycles == [], cycles
    assert order.index('a') < order.index('c')
    assert order.index('b') < order.index('c')


def test_cycle_detection():
    plugins = {'a': {'b'}, 'b': {'a'}}
    order, cycles = resolve_dependency_order(plugins)
    assert order == [], order
    assert len(cycles) == 1, cycles
    assert set(cycles[0]) == {'a', 'b'}, cycles


def test_cycle_with_normal():
    plugins = {'a': {'b'}, 'b': {'a'}, 'ok': set(), 'need': {'ok'}}
    order, cycles = resolve_dependency_order(plugins)
    assert set(order) == {'ok', 'need'}, order
    assert len(cycles) == 1, cycles
    assert set(cycles[0]) == {'a', 'b'}, cycles


def test_missing_dep_excluded_from_order():
    """缺失依赖不在图中（由调用方预滤），不进入拓扑序。"""
    plugins = {'a': {'missing'}, 'b': set()}
    # 调用方把缺失依赖的插件标记后，a 不参与拓扑（此处 a 依赖 missing，不在图内）
    filtered = {n: ds for n, ds in plugins.items() if all(d in plugins for d in ds)}
    order, cycles = resolve_dependency_order(filtered)
    assert 'b' in order and 'a' not in order, order


def run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f'PASS {fn.__name__}')
            passed += 1
        except AssertionError as e:
            print(f'FAIL {fn.__name__}: {e}')
        except Exception as e:
            print(f'ERROR {fn.__name__}: {type(e).__name__}: {e}')
    print(f'\n通过 {passed}/{len(fns)}')
    return 0 if passed == len(fns) else 1


if __name__ == '__main__':
    sys.exit(run())
