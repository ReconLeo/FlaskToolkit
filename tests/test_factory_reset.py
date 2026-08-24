# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""Factory Reset 范围与内置插件保护单元测试（纯函数 + 隔离目录，不依赖 Flask 服务）

通过 mock global_var.BASE_DIR / FRONTEND_TEMPLATE_DIR / FRONTEND_CONFIG_FILE 到临时目录，
直接调用 core.factory_reset.factory_reset(scope)，验证：
- 各 scope 的删除范围与保留范围（内置插件 auth/user_manage、base_plugin、status.json 受保护）
- all 范围额外重置内置插件配置（auth users 清空）
- 空列表 / 非法 scope 无副作用
- 空目录（无 plugins/）不报错

运行：python test_factory_reset.py
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, _PROJECT_ROOT)

import global_var
from core.factory_reset import factory_reset

results = []

def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

def make_tree(root):
    """构造一份完整可重置的隔离项目目录，返回关键路径"""
    def w(path, content=''):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    # plugins/（内置 + 自定义 + 元数据）
    w(os.path.join(root, 'plugins', '__init__.py'))
    w(os.path.join(root, 'plugins', 'base_plugin.py'), 'class BasePlugin: pass')
    w(os.path.join(root, 'plugins', 'auth.py'), 'class AuthPlugin: pass')
    w(os.path.join(root, 'plugins', 'user_manage.py'), 'class UserManagePlugin: pass')
    w(os.path.join(root, 'plugins', 'demo_custom.py'), 'class DemoPlugin: pass')
    w(os.path.join(root, 'plugins', 'demo_custom.json'), '{"name": "demo_custom"}')
    w(os.path.join(root, 'plugins', 'status.json'), '{}')
    # plugins/configs + plugins/data
    auth_cfg = os.path.join(root, 'plugins', 'configs', 'auth.json')
    w(auth_cfg, json.dumps({"SESSION_EXPIRE": 86400, "users": [
        {"id": 1, "username": "admin", "password": "x", "role": "admin"}
    ]}))
    w(os.path.join(root, 'plugins', 'data', 'sessions.json'), '{"s1": {}}')
    # plugins/temp：内置受保护子目录 + 自定义子目录
    w(os.path.join(root, 'plugins', 'temp', 'auth', 't'), 'x')
    w(os.path.join(root, 'plugins', 'temp', 'demo_custom', 't'), 'x')
    # templates/plugins：内置模板 + 自定义模板 + 静态
    w(os.path.join(root, 'templates', 'plugins', 'auth.html'))
    w(os.path.join(root, 'templates', 'plugins', 'user_manage.html'))
    w(os.path.join(root, 'templates', 'plugins', 'demo_custom.html'))
    w(os.path.join(root, 'templates', 'plugins', 'static', 'auth', 'a.js'))
    w(os.path.join(root, 'templates', 'plugins', 'static', 'demo_custom', 'd.js'))
    # templates/frontend_tools
    w(os.path.join(root, 'templates', 'frontend_tools', 'demo_tool.html'))
    w(os.path.join(root, 'templates', 'frontend_tools', 'static', 'demo_tool', 'x.css'))
    # 其它可重置数据
    w(os.path.join(root, 'frontend_tools.json'), '[{"name": "demo_tool"}]')
    w(os.path.join(root, 'data', 'stats.json'), '{"call_stats": {"a": 1}}')
    w(os.path.join(root, 'logs', 'app.log'), 'log-line')
    w(os.path.join(root, 'temp', 'tmp.zip'), 'x')
    w(os.path.join(root, '.plugin_cache', 'c.json'), '{}')
    w(os.path.join(root, 'plugins', '__pycache__', 'auth.cpython.pyc'), 'x')
    return auth_cfg


def _mock_env(root, mock=('BASE_DIR', 'FRONTEND_TEMPLATE_DIR', 'FRONTEND_CONFIG_FILE')):
    saved = {a: getattr(global_var, a, None) for a in mock}
    if 'BASE_DIR' in mock:
        global_var.BASE_DIR = root
    if 'FRONTEND_TEMPLATE_DIR' in mock:
        global_var.FRONTEND_TEMPLATE_DIR = os.path.join(root, 'templates', 'frontend_tools')
    if 'FRONTEND_CONFIG_FILE' in mock:
        global_var.FRONTEND_CONFIG_FILE = os.path.join(root, 'frontend_tools.json')
    return saved

def _restore_env(saved):
    for a, v in saved.items():
        if v is None:
            try:
                delattr(global_var, a)
            except AttributeError:
                pass
        else:
            setattr(global_var, a, v)

def _cleanup(root):
    try:
        shutil.rmtree(root, ignore_errors=True)
    except Exception:
        pass


def test_plugins_scope():
    root = tempfile.mkdtemp(prefix='ftk_fr_plugins_')
    saved = _mock_env(root)
    try:
        make_tree(root)
        results_ = factory_reset('plugins')
        cleaned = results_['cleaned']
        # 自定义插件文件被删
        check('plugins scope 删自定义 .py',
              not os.path.exists(os.path.join(root, 'plugins', 'demo_custom.py')), '')
        check('plugins scope 删自定义 .json',
              not os.path.exists(os.path.join(root, 'plugins', 'demo_custom.json')), '')
        # 内置受保护
        check('plugins scope 保留内置 auth.py',
              os.path.exists(os.path.join(root, 'plugins', 'auth.py')), '')
        check('plugins scope 保留内置 user_manage.py',
              os.path.exists(os.path.join(root, 'plugins', 'user_manage.py')), '')
        # base_plugin / __init__ / status.json 保留
        check('plugins scope 保留 base_plugin.py',
              os.path.exists(os.path.join(root, 'plugins', 'base_plugin.py')), '')
        check('plugins scope 保留 status.json',
              os.path.exists(os.path.join(root, 'plugins', 'status.json')), '')
        # 模板/静态：自定义删、内置留
        check('plugins scope 删自定义模板',
              not os.path.exists(os.path.join(root, 'templates', 'plugins', 'demo_custom.html')), '')
        check('plugins scope 保留内置模板 auth.html',
              os.path.exists(os.path.join(root, 'templates', 'plugins', 'auth.html')), '')
        check('plugins scope 删自定义静态目录',
              not os.path.exists(os.path.join(root, 'templates', 'plugins', 'static', 'demo_custom')), '')
        # plugins/temp：自定义子目录删、内置子目录留
        check('plugins scope 删自定义插件临时目录',
              not os.path.exists(os.path.join(root, 'plugins', 'temp', 'demo_custom')), '')
        check('plugins scope 保留内置插件临时目录',
              os.path.exists(os.path.join(root, 'plugins', 'temp', 'auth')), '')
        # 其它范围数据不动
        check('plugins scope 不动 frontend_tools',
              os.path.exists(os.path.join(root, 'templates', 'frontend_tools', 'demo_tool.html')), '')
        check('plugins scope 不动 stats',
              os.path.exists(os.path.join(root, 'data', 'stats.json')), '')
        check('plugins scope 返回 cleaned 非空', len(cleaned) > 0, f'cleaned={len(cleaned)}')
    finally:
        _restore_env(saved)
        _cleanup(root)


def test_frontend_tools_scope():
    root = tempfile.mkdtemp(prefix='ftk_fr_frontend_')
    saved = _mock_env(root)
    try:
        make_tree(root)
        factory_reset('frontend_tools')
        # 清单清空 + 模板目录清空
        cfg = json.load(open(os.path.join(root, 'frontend_tools.json'), encoding='utf-8'))
        check('frontend_tools scope 清单清空', cfg == [], f'cfg={cfg}')
        check('frontend_tools scope 模板目录清空',
              not os.path.exists(os.path.join(root, 'templates', 'frontend_tools', 'demo_tool.html')), '')
        # 插件不受影响
        check('frontend_tools scope 不动插件',
              os.path.exists(os.path.join(root, 'plugins', 'demo_custom.py')), '')
    finally:
        _restore_env(saved)
        _cleanup(root)


def test_stats_logs_scope():
    root = tempfile.mkdtemp(prefix='ftk_fr_stats_')
    saved = _mock_env(root)
    try:
        make_tree(root)
        global_var.call_stats.clear()
        global_var.call_stats['x'] = 5
        factory_reset('stats_logs')
        stats = json.load(open(os.path.join(root, 'data', 'stats.json'), encoding='utf-8'))
        check('stats_logs scope 统计重置', stats == {'call_stats': {}, 'frontend_access_stats': {}},
              f'keys={list(stats.keys())}')
        check('stats_logs scope 内存统计清空', global_var.call_stats == {}, f'{global_var.call_stats}')
        check('stats_logs scope 日志目录清空',
              not os.path.exists(os.path.join(root, 'logs', 'app.log')), '')
        # sessions 不受影响
        check('stats_logs scope 不动 sessions',
              os.path.exists(os.path.join(root, 'plugins', 'data', 'sessions.json')), '')
    finally:
        _restore_env(saved)
        _cleanup(root)


def test_sessions_scope():
    root = tempfile.mkdtemp(prefix='ftk_fr_sessions_')
    saved = _mock_env(root)
    try:
        make_tree(root)
        factory_reset('sessions')
        s = json.load(open(os.path.join(root, 'plugins', 'data', 'sessions.json'), encoding='utf-8'))
        check('sessions scope 会话清空', s == {}, f's={s}')
        check('sessions scope 不动插件',
              os.path.exists(os.path.join(root, 'plugins', 'demo_custom.py')), '')
    finally:
        _restore_env(saved)
        _cleanup(root)


def test_temp_scope():
    root = tempfile.mkdtemp(prefix='ftk_fr_temp_')
    saved = _mock_env(root)
    try:
        make_tree(root)
        factory_reset('temp')
        check('temp scope 清空 temp/',
              not os.path.exists(os.path.join(root, 'temp', 'tmp.zip')), '')
        check('temp scope 清空 .plugin_cache',
              not os.path.exists(os.path.join(root, '.plugin_cache', 'c.json')), '')
        check('temp scope 清空 __pycache__',
              not os.path.exists(os.path.join(root, 'plugins', '__pycache__')), '')
        check('temp scope 不动插件',
              os.path.exists(os.path.join(root, 'plugins', 'demo_custom.py')), '')
    finally:
        _restore_env(saved)
        _cleanup(root)


def test_all_scope():
    root = tempfile.mkdtemp(prefix='ftk_fr_all_')
    saved = _mock_env(root)
    try:
        auth_cfg = make_tree(root)
        factory_reset('all')
        # 自定义插件 + 前端工具 + stats + sessions + temp 全清
        check('all scope 删自定义插件',
              not os.path.exists(os.path.join(root, 'plugins', 'demo_custom.py')), '')
        check('all scope 清前端工具模板',
              not os.path.exists(os.path.join(root, 'templates', 'frontend_tools', 'demo_tool.html')), '')
        check('all scope 清日志',
              not os.path.exists(os.path.join(root, 'logs', 'app.log')), '')
        # 内置插件文件仍在（受保护）
        check('all scope 保留内置 auth.py',
              os.path.exists(os.path.join(root, 'plugins', 'auth.py')), '')
        # builtin 范围：auth.json users 清空
        cfg = json.load(open(auth_cfg, encoding='utf-8'))
        check('all scope 重置内置配置 auth users 清空', cfg['users'] == [], f'users={cfg["users"]}')
        # 清理结果合并
        res = factory_reset  # noqa
    finally:
        _restore_env(saved)
        _cleanup(root)


def test_empty_and_invalid_scope():
    root = tempfile.mkdtemp(prefix='ftk_fr_empty_')
    saved = _mock_env(root)
    try:
        make_tree(root)
        # 空列表：无任何 scope 执行
        r = factory_reset([])
        check('空列表 scope 无清理', r['cleaned'] == [] and r['failed'] == [], f'{r}')
        check('空列表后插件仍在',
              os.path.exists(os.path.join(root, 'plugins', 'demo_custom.py')), '')
        # 非法字符串 scope
        r = factory_reset('bogus')
        check('非法 scope 无清理', r['cleaned'] == [] and r['failed'] == [], f'{r}')
        # 非法列表项被过滤
        r = factory_reset(['plugins', 'bogus'])
        check('混合列表仅保留合法项', r['cleaned'] != [] and 'bogus' not in ' '.join(r['cleaned']),
              f'{r}')
    finally:
        _restore_env(saved)
        _cleanup(root)


def test_empty_dir_safe():
    root = tempfile.mkdtemp(prefix='ftk_fr_empty_dir_')
    saved = _mock_env(root)
    try:
        # 空目录（无 plugins/、无 frontend_tools 等）
        r = factory_reset('all')
        check('空目录 all scope 不报错', isinstance(r, dict) and 'cleaned' in r, f'{r}')
    finally:
        _restore_env(saved)
        _cleanup(root)


if __name__ == '__main__':
    test_plugins_scope()
    test_frontend_tools_scope()
    test_stats_logs_scope()
    test_sessions_scope()
    test_temp_scope()
    test_all_scope()
    test_empty_and_invalid_scope()
    test_empty_dir_safe()

    passed = sum(1 for _, c, _ in results if c)
    print(f"\n==== Factory Reset 范围测试 共 {len(results)} 项，通过 {passed}，失败 {len(results) - passed} ====")
    sys.exit(0 if passed == len(results) else 1)
