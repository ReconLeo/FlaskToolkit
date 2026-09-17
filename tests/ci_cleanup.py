# -*- coding: utf-8 -*-
"""CI 测试间清理脚本：还原测试可能污染的真实项目状态，防止测试之间互相影响。

用法（在 CI 循环内、每个测试后调用）：
    python tests/ci_cleanup.py

清理范围（与回归测试可能写盘的范围对齐）：
- plugins/configs/auth.json：仅保留 admin 用户
- plugins/data/auth/sessions.json：清空（v4.5.0 起 auth 会话迁移至插件自属目录）
- plugins/status.json：清空
- data/stats.json：保留（统计不影响权限测试）
- temp/、.plugin_cache/：清理临时文件/缓存
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import global_var

cleaned = []


def _safe_remove(path):
    try:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        elif os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def cleanup():
    # 1. auth.json 仅保留 admin
    auth = os.path.join(global_var.PLUGIN_CONFIGS_DIR, 'auth.json')
    if os.path.exists(auth):
        try:
            d = json.load(open(auth, encoding='utf-8'))
            d['users'] = [u for u in d.get('users', []) if u.get('username') == 'admin']
            json.dump(d, open(auth, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
            cleaned.append('auth.json')
        except Exception:
            pass
    # 2. sessions / status 重置（v4.5.0：auth 会话位于 plugins/data/auth/）
    for rel in (os.path.join('plugins', 'data', 'auth', 'sessions.json'),
                os.path.join('plugins', 'status.json')):
        p = os.path.join(global_var.BASE_DIR, rel)
        if os.path.exists(p):
            try:
                open(p, 'w', encoding='utf-8').write('{}')
                cleaned.append(rel)
            except Exception:
                pass
    # 3. temp / .plugin_cache 清理（含隔离目录 temp/_iso_*、demo zip 等测试产物）
    for rel in ('temp', '.plugin_cache'):
        p = os.path.join(global_var.BASE_DIR, rel)
        if os.path.isdir(p):
            _safe_remove(p)
            cleaned.append(rel)

    base = global_var.BASE_DIR
    builtin = global_var.BUILTIN_PLUGINS

    # 4. data/audit.log：测试会写审计日志，逐轮清理避免残留累积
    _audit = os.path.join(base, 'data', 'audit.log')
    if os.path.isfile(_audit):
        _safe_remove(_audit)
        cleaned.append('data/audit.log')

    # 5. plugins/temp/：清空非内置插件临时子目录（v4.21 目录化各插件运行时 temp），内置插件保留
    _pt = os.path.join(base, 'plugins', 'temp')
    if os.path.isdir(_pt):
        for sub in sorted(os.listdir(_pt)):
            if sub in builtin:
                continue
            _safe_remove(os.path.join(_pt, sub))
            cleaned.append('plugins/temp/' + sub)

    # 6. plugins/data/：清空非内置插件数据目录（保留内置插件数据）
    _pd = os.path.join(base, 'plugins', 'data')
    if os.path.isdir(_pd):
        for fn in sorted(os.listdir(_pd)):
            if fn in builtin:
                continue
            _safe_remove(os.path.join(_pd, fn))
            cleaned.append('plugins/data/' + fn)

    # 7. templates/plugins/：清除非内置插件模板残留（保留 user_manage 模板与 static），修复 static 整删
    _tpl = os.path.join(base, 'templates', 'plugins')
    if os.path.isdir(_tpl):
        for fn in sorted(os.listdir(_tpl)):
            if fn == 'static':
                continue
            name = fn[:-5] if fn.endswith('.html') else fn
            if name in builtin:
                continue
            _safe_remove(os.path.join(_tpl, fn))
            cleaned.append('templates/plugins/' + fn)
        _st = os.path.join(_tpl, 'static')
        if os.path.isdir(_st):
            for fn in sorted(os.listdir(_st)):
                if fn in builtin:
                    continue
                _safe_remove(os.path.join(_st, fn))
                cleaned.append('templates/plugins/static/' + fn)

    print(f"[ci_cleanup] 已清理: {', '.join(cleaned) or '无'} ")


if __name__ == '__main__':
    cleanup()
