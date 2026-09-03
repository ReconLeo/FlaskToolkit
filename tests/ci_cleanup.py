# -*- coding: utf-8 -*-
"""CI 测试间清理脚本：还原测试可能污染的真实项目状态，防止测试之间互相影响。

用法（在 CI 循环内、每个测试后调用）：
    python tests/ci_cleanup.py

清理范围（与回归测试可能写盘的范围对齐）：
- plugins/configs/auth.json：仅保留 admin 用户
- plugins/data/sessions.json：清空
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
    # 3. temp / .plugin_cache 清理
    for rel in ('temp', '.plugin_cache'):
        p = os.path.join(global_var.BASE_DIR, rel)
        if os.path.isdir(p):
            _safe_remove(p)
            cleaned.append(rel)
    print(f"[ci_cleanup] 已清理: {', '.join(cleaned) or '无'} ")


if __name__ == '__main__':
    cleanup()
