# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""版本更新机制测试（v4.8.0，F1/F4）

覆盖：
- 版本号解析与比较（parse_version / is_newer，含 v 前缀、非数字段容错）
- 用户数据路径判定（tools/update.py path_is_user_data，与 .gitignore 语义对齐）
- zip slip 防护（check_zip_slip：绝对路径 / 上级目录穿越拒绝）
- 更新包校验链（verify_update_archive：sha256 必选比对、manifest 版本一致性、zip slip）
- 版本检查缓存（update_checker：缓存 TTL 生效 / force 跳过 / 缓存读写）
- changelog 数据源结构校验（缺字段拒绝）
- archive 替换保留用户数据（解压目录路径判定，data/plugins/configs 等保留）

运行：python test_update_checker.py
"""
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import time
import zipfile

REAL_BASE = _PROJECT_ROOT
sys.path.insert(0, REAL_BASE)

import global_var
from core.update_checker import (
    parse_version, is_newer, UpdateInfo, check_for_update,
    _cache_file, _read_cache, _write_cache, _cache_fresh,
)
from tools.update import (
    path_is_user_data, check_zip_slip, sha256_file, verify_update_archive,
)

results = []

def check(name, cond, detail=''):
    results.append((name, cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

def build_test_zip(path, manifest_version, include_slip=False):
    """构造更新包：global_var.py + manifest.json（可选 zip slip 成员）"""
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('global_var.py', 'FRAMEWORK_VERSION = "9.9.9"')
        zf.writestr('app.py', '# test')
        zf.writestr('manifest.json', json.dumps({
            'schema_version': '1.0', 'package_type': 'framework-runtime',
            'version': manifest_version, 'required_python': '3.10+',
            'files': {'global_var.py': 'x', 'app.py': 'x'}}, ensure_ascii=False))
        if include_slip:
            zf.writestr('../evil.py', '# evil')

def build_changelog(path, version='9.9.9', sha256='', download_url='', changes=None):
    with io.open(path, 'w', encoding='utf-8') as f:
        json.dump({
            'latest_version': version,
            'published_at': '2026-09-05',
            'download_url': download_url,
            'sha256': sha256,
            'changes': changes or ['测试变更'],
        }, f, ensure_ascii=False, indent=2)

# ---------- 1. 版本解析与比较 ----------
check('parse_version 4.8.0', parse_version('4.8.0') == (4, 8, 0))
check('parse_version v 前缀', parse_version('v4.7.0') == (4, 7, 0))
check('parse_version 多段', parse_version('4.10.0') == (4, 10, 0))
check('parse_version 非法段', parse_version('4.a.0') == (4, 0, 0))
check('is_newer 大版本', is_newer('5.0.0', '4.9.9'))
check('is_newer 次版本', is_newer('4.8.0', '4.7.9'))
check('is_newer 补丁', is_newer('4.7.1', '4.7.0'))
check('is_newer 相等', not is_newer('4.7.0', '4.7.0'))
check('is_newer 反向', not is_newer('4.7.0', '4.8.0'))

# ---------- 2. 用户数据路径判定 ----------
check('保留 data/', path_is_user_data('data/user_config.json'))
check('保留 data 根文件', path_is_user_data('data/stats.json'))
check('保留 plugins/configs', path_is_user_data('plugins/configs/auth.json'))
check('保留 plugins/data', path_is_user_data('plugins/data/corp_tools/x.json'))
check('保留 plugins/temp', path_is_user_data('plugins/temp/xxx'))
check('保留 logs', path_is_user_data('logs/app.log'))
check('保留 .plugin_cache', path_is_user_data('.plugin_cache/cache.json'))
check('保留 workspace', path_is_user_data('workspace/fix.py'))
check('保留 temp', path_is_user_data('temp/update_downloads/x.zip'))
check('保留 frontend_tools.json', path_is_user_data('frontend_tools.json'))
check('保留 plugins/status.json', path_is_user_data('plugins/status.json'))
check('保留 users（AI 助手本地数据）', path_is_user_data('users/379905073/projects/_index.json'))
check('locales 属框架内置（非用户数据，随更新携带）', not path_is_user_data('locales/en.json'))
check('locales 属框架内置（含扩展语言包）', not path_is_user_data('locales/fr.json'))
check('不保留 app.py', not path_is_user_data('app.py'))
check('不保留 core', not path_is_user_data('core/update_checker.py'))
check('不保留 内置插件', not path_is_user_data('plugins/base_plugin.py'))
check('不保留 templates', not path_is_user_data('templates/admin/base.html'))

# ---------- 3. zip slip 防护 ----------
ok, bad = check_zip_slip(['app.py', 'core/x.py'])
check('zip slip 正常包放行', ok and not bad)
ok2, bad2 = check_zip_slip(['app.py', '../evil.py'])
check('zip slip 穿越拒绝', not ok2 and bad2 == '../evil.py')
ok3, bad3 = check_zip_slip(['/abs/path.py'])
check('zip slip 绝对路径拒绝', not ok3)

# ---------- 4. 更新包校验链 ----------
iso = tempfile.mkdtemp(prefix='ftk_upd_')
try:
    # sha256 匹配 + manifest 一致 → 通过
    z1 = os.path.join(iso, 'ok.zip')
    build_test_zip(z1, '9.9.9')
    ch1 = os.path.join(iso, 'ch1.json')
    build_changelog(ch1, sha256=sha256_file(z1))
    changelog1 = json.load(io.open(ch1, encoding='utf-8'))
    okv, msgv = verify_update_archive(z1, changelog1, global_var)
    check('校验链 通过', okv and '通过' in msgv, msgv)

    # sha256 不匹配 → 拒绝
    ch2 = os.path.join(iso, 'ch2.json')
    build_changelog(ch2, sha256='0' * 64)
    changelog2 = json.load(io.open(ch2, encoding='utf-8'))
    okv2, msgv2 = verify_update_archive(z1, changelog2, global_var)
    check('校验链 sha256 不匹配拒绝', not okv2 and 'sha256' in msgv2, msgv2)

    # changelog 缺 sha256 → 拒绝
    ch3 = os.path.join(iso, 'ch3.json')
    build_changelog(ch3, sha256='')
    changelog3 = json.load(io.open(ch3, encoding='utf-8'))
    okv3, msgv3 = verify_update_archive(z1, changelog3, global_var)
    check('校验链 缺 sha256 拒绝', not okv3 and 'sha256' in msgv3, msgv3)

    # manifest 版本不一致 → 拒绝（changelog sha256 指向 z2 自身，先过 sha256 再查版本）
    z2 = os.path.join(iso, 'ver.zip')
    build_test_zip(z2, '9.9.8')
    ch2v = os.path.join(iso, 'ch2v.json')
    build_changelog(ch2v, sha256=sha256_file(z2))
    changelog2v = json.load(io.open(ch2v, encoding='utf-8'))
    okv4, msgv4 = verify_update_archive(z2, changelog2v, global_var)
    check('校验链 manifest 版本不一致拒绝', not okv4 and '不一致' in msgv4, msgv4)

    # zip slip 成员 → 拒绝
    z3 = os.path.join(iso, 'slip.zip')
    build_test_zip(z3, '9.9.9', include_slip=True)
    ch3v = os.path.join(iso, 'ch3v.json')
    build_changelog(ch3v, sha256=sha256_file(z3))
    changelog3v = json.load(io.open(ch3v, encoding='utf-8'))
    okv5, msgv5 = verify_update_archive(z3, changelog3v, global_var)
    check('校验链 zip slip 拒绝', not okv5 and 'slip' in msgv5.lower(), msgv5)

    # 无效 zip → 拒绝
    z4 = os.path.join(iso, 'bad.zip')
    with open(z4, 'wb') as f:
        f.write(b'not a zip')
    okv6, msgv6 = verify_update_archive(z4, changelog1, global_var)
    check('校验链 无效 zip 拒绝', not okv6, msgv6)

    # ---------- 5. 版本检查缓存 ----------
    saved_base = global_var.BASE_DIR
    saved_user_cfg = dict(global_var._user_config)
    global_var.BASE_DIR = iso
    global_var._user_config['UPDATE_CHECK_INTERVAL'] = 24
    info = UpdateInfo(latest_version='9.9.9', changes=['缓存测试'])
    _write_cache(info)
    check('缓存写入', _cache_file() and os.path.exists(_cache_file()))
    cached = _read_cache()
    check('缓存读取', cached and cached['latest_version'] == '9.9.9')
    fresh = _cache_fresh(force=False)
    check('缓存未过期返回', fresh and fresh.latest_version == '9.9.9')
    fresh2 = _cache_fresh(force=True)
    check('force 跳过缓存', fresh2 is None)
    # 过期：interval 0 → 缓存视为过期
    global_var._user_config['UPDATE_CHECK_INTERVAL'] = 0
    fresh3 = _cache_fresh(force=False)
    check('TTL 过期失效', fresh3 is None)
    global_var._user_config['UPDATE_CHECK_INTERVAL'] = 24
    global_var.BASE_DIR = saved_base
    global_var._user_config = saved_user_cfg

    # ---------- 6. changelog 数据源结构校验 ----------
    ch_bad = os.path.join(iso, 'bad_feed.json')
    with io.open(ch_bad, 'w', encoding='utf-8') as f:
        json.dump({'foo': 1}, f)
    ch_ok = os.path.join(iso, 'good_feed.json')
    build_changelog(ch_ok, sha256='x')
    # 通过 file:// 拉取（先清理缓存，避免坏数据源失败后回退旧缓存干扰断言）
    saved2 = global_var.BASE_DIR
    global_var.BASE_DIR = iso
    _cf = _cache_file()
    if os.path.exists(_cf):
        os.remove(_cf)
    r1 = check_for_update(force=True, feed_url='file:///' + ch_bad.replace('\\', '/'))
    check('缺字段数据源返回 None', r1 is None)
    # 合法数据源（无 sha256 校验要求，仅结构）→ 返回 UpdateInfo
    r2 = check_for_update(force=True, feed_url='file:///' + ch_ok.replace('\\', '/'))
    check('合法数据源返回信息', r2 is not None and r2.latest_version == '9.9.9', repr(r2.latest_version if r2 else None))
    global_var.BASE_DIR = saved2
finally:
    shutil.rmtree(iso, ignore_errors=True)

print(f"\n==== 版本更新机制测试 共 {len(results)} 项，通过 {sum(1 for _, c in results if c)}，失败 {sum(1 for _, c in results if not c)} ====")
sys.exit(0 if all(c for _, c in results) else 1)
