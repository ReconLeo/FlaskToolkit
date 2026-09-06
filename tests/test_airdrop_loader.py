# -*- coding: utf-8 -*-
"""AirDrop 插件加载回归（v4.10 修复：routes 缺 @property 导致 load_plugins 加载失败）

背景：plugins/airdrop.py 的 `def routes(self)` 未加 @property（基类为 @property @abstractmethod），
真实 load_plugins 中 `for route in plugin_instance.routes` 拿到 bound method → TypeError
"'method' object is not iterable"，airdrop 无法加载。此前测试均不加载真实 airdrop 未暴露。

场景（隔离目录，不污染真实项目）：
A. load_plugins 成功加载 airdrop（routes 为属性而非方法）
B. routes 结构：9 条路由；upload 带 route 级 max_upload；含路径参数路由
C. 页面路由 /plugin/airdrop 可访问（索引页 200）
D. API /api/airdrop/network-addresses 可访问（public，auth 未装放行）

运行：python tests/test_airdrop_loader.py
"""
import os
import shutil
import sys
import tempfile

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_TESTS_DIR)
sys.path.insert(0, _PROJECT_ROOT)

# AirDrop 插件文件（plugins/airdrop.py 及模板）在 .gitignore 中有意排除——属独立子项目，
# 不入 FlaskToolkit 仓库（CI clone 后不存在）。本地存在时运行本回归，缺失时跳过。
if not os.path.exists(os.path.join(_PROJECT_ROOT, 'plugins', 'airdrop.py')):
    print("SKIP: plugins/airdrop.py 不存在（AirDrop 插件不入库，本地存在时运行本回归）")
    sys.exit(0)

import global_var

results = []

def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")


def build_env():
    """隔离环境：复制 airdrop/base_plugin 骨架 + patch global_var 路径常量（含插件缓存文件）"""
    root = tempfile.mkdtemp(prefix='ftk_airdrop_')
    os.makedirs(os.path.join(root, 'plugins'))
    os.makedirs(os.path.join(root, 'temp'))
    for fn in ('__init__.py', 'base_plugin.py', 'airdrop.py'):
        shutil.copy(os.path.join(_PROJECT_ROOT, 'plugins', fn),
                    os.path.join(root, 'plugins', fn))
    # 清理 plugins 模块缓存：避免本进程此前导入的真实 plugins 包残留
    for _m in [m for m in list(sys.modules) if m == 'plugins' or m.startswith('plugins.')]:
        del sys.modules[_m]
    sys.path.insert(0, root)
    saved = {}
    for attr, val in (('BASE_DIR', root), ('UPLOAD_TEMP_DIR', os.path.join(root, 'temp')),
                      ('STATS_FILE', os.path.join(root, 'data', 'stats.json')),
                      ('PLUGIN_CACHE_DIR', os.path.join(root, '.plugin_cache')),
                      ('PLUGIN_CACHE_FILE', os.path.join(root, '.plugin_cache', 'plugin_discovery_cache.json'))):
        saved[attr] = getattr(global_var, attr, None)
        setattr(global_var, attr, val)
    return root, saved


def restore_env(saved, root):
    for attr, val in saved.items():
        if val is None:
            try:
                delattr(global_var, attr)
            except AttributeError:
                pass
        else:
            setattr(global_var, attr, val)
    try:
        shutil.rmtree(root, ignore_errors=True)
    except Exception:
        pass


def main():
    root, saved = build_env()
    try:
        import app as appmod
        from core.plugin_loader import load_plugins
        app = appmod.app
        app.config["TESTING"] = True
        from jinja2 import ChoiceLoader, FileSystemLoader
        app.jinja_env.loader = ChoiceLoader([
            FileSystemLoader(os.path.join(root, 'templates')),
            FileSystemLoader(os.path.join(_PROJECT_ROOT, 'templates')),
        ])
        load_plugins()
        client = app.test_client()

        # ---------- A. airdrop 成功加载 ----------
        ad = global_var.plugins.get('airdrop')
        check("A1 airdrop 插件加载成功", ad is not None, f"plugins={list(global_var.plugins.keys())}")
        check("A2 routes 是属性（可迭代列表）", ad is not None and isinstance(ad.routes, list),
              f"type={type(ad.routes).__name__ if ad else 'None'}")

        # ---------- B. routes 结构 ----------
        if ad is not None:
            routes = ad.routes
            check("B1 路由数量为 9", len(routes) == 9, f"count={len(routes)}")
            paths = {r['path'] for r in routes}
            check("B2 含核心路由",
                  {'/network-addresses', '/files', '/upload', '/download/<filename>'} <= paths,
                  f"paths={sorted(paths)}")
            upload_route = next((r for r in routes if r['path'] == '/upload'), None)
            check("B3 upload 带 route 级 max_upload",
                  upload_route is not None and upload_route.get('max_upload') == int(ad.max_gb * 1024),
                  f"max_upload={upload_route.get('max_upload') if upload_route else None}")
            check("B4 含路径参数路由", any('<' in r['path'] for r in routes), '')

        # ---------- C. 页面路由 ----------
        r = client.get('/plugin/airdrop')
        check("C1 /plugin/airdrop 索引页 200", r.status_code == 200, f"status={r.status_code}")

        # ---------- D. API 路由 ----------
        r = client.get('/api/airdrop/network-addresses')
        check("D1 /api/airdrop/network-addresses 200", r.status_code == 200, f"status={r.status_code}")

        print(f'\n==== AirDrop 插件加载回归（routes @property 修复）：共 {len(results)} 项，'
              f'通过 {sum(1 for _, c, _ in results if c)}，'
              f'失败 {sum(1 for _, c, _ in results if not c)} ====')
    finally:
        restore_env(saved, root)

    ok = all(c for _, c, _ in results)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
