# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""发布签名联动测试（v4.8.0 发布工具链 + v4.15 更新源签名）

覆盖 tools/release.py write_changelog --sign 产出的签名 changelog，
能被 core/update_checker.check_for_update 用对应公钥验证通过（端到端闭环）：
- write_changelog(private_key) 生成含 signature 的 changelog
- 配置 UPDATE_PUBLIC_KEY_PEM + 该 changelog → check_for_update 通过返回最新版本
- 篡改签名 changelog → check_for_update 拒绝（返回 None）
- 错误公钥 → 拒绝

运行：python test_release_sign.py
"""
import io
import json
import os
import shutil
import sys
import tempfile

REAL_BASE = _PROJECT_ROOT
sys.path.insert(0, REAL_BASE)

import global_var
from core.update_checker import check_for_update, _cache_file, _read_cache
from tools.release import write_changelog

results = []

def check(name, cond, detail=''):
    results.append((name, cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

iso = tempfile.mkdtemp(prefix='ftk_rel_')
try:
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_path = os.path.join(iso, 'private.pem')
    pub_path = os.path.join(iso, 'public.pem')
    with open(priv_path, 'wb') as f:
        f.write(priv.private_bytes(serialization.Encoding.PEM,
                                   serialization.PrivateFormat.PKCS8,
                                   serialization.NoEncryption()))
    with open(pub_path, 'wb') as f:
        f.write(priv.public_key().public_bytes(serialization.Encoding.PEM,
                                               serialization.PublicFormat.SubjectPublicKeyInfo))

    # 保存全局状态
    saved_base = global_var.BASE_DIR
    saved_key = global_var._user_config.get('UPDATE_PUBLIC_KEY_PEM')
    saved_iv = global_var._user_config.get('UPDATE_CHECK_INTERVAL')
    global_var.BASE_DIR = iso
    global_var._user_config['UPDATE_CHECK_INTERVAL'] = 0

    def clear_cache():
        p = _cache_file()
        if os.path.exists(p):
            os.remove(p)

    # ---------- 1. write_changelog 签名产出含 signature ----------
    feed_path = os.path.join(iso, 'changelog.json')
    write_changelog('9.9.9', ['发布签名联动测试'], 'http://example.com/flasktoolkit-9.9.9.zip',
                    'abcd1234', out_path=feed_path, private_key=priv_path)
    cl = json.load(io.open(feed_path, encoding='utf-8'))
    check('发布：--sign 产出含 signature', 'signature' in cl
          and cl['signature']['algorithm'] == 'RSA-SHA256'
          and cl['signature'].get('signer') == 'FlaskToolkit-release')

    # ---------- 2. 配置公钥 + 该 changelog → 验证通过 ----------
    global_var._user_config['UPDATE_PUBLIC_KEY_PEM'] = pub_path
    clear_cache()
    info = check_for_update(force=True, feed_url='file:///' + feed_path.replace('\\', '/'))
    check('发布→更新：公钥验证签名 changelog 通过',
          info is not None and info.latest_version == '9.9.9',
          'None' if info is None else '')

    # ---------- 3. 篡改签名 changelog → 拒绝 ----------
    _t = json.load(io.open(feed_path, encoding='utf-8'))
    _t['latest_version'] = '10.0.0'
    tamper_path = os.path.join(iso, 'tamper.json')
    with io.open(tamper_path, 'w', encoding='utf-8') as f:
        json.dump(_t, f, ensure_ascii=False)
    clear_cache()
    info2 = check_for_update(force=True, feed_url='file:///' + tamper_path.replace('\\', '/'))
    check('发布→更新：篡改签名 changelog 拒绝', info2 is None)
    check('发布→更新：签名失败不写缓存',
          not (os.path.exists(_cache_file()) and _read_cache().get('latest_version') == '10.0.0'))

    # ---------- 4. 错误公钥 → 拒绝 ----------
    _other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    wrong_path = os.path.join(iso, 'wrong.pem')
    with open(wrong_path, 'wb') as f:
        f.write(_other.public_key().public_bytes(serialization.Encoding.PEM,
                                                 serialization.PublicFormat.SubjectPublicKeyInfo))
    global_var._user_config['UPDATE_PUBLIC_KEY_PEM'] = wrong_path
    clear_cache()
    info3 = check_for_update(force=True, feed_url='file:///' + feed_path.replace('\\', '/'))
    check('发布→更新：错误公钥拒绝', info3 is None)

    # 恢复全局状态
    global_var.BASE_DIR = saved_base
    if saved_key is None:
        global_var._user_config.pop('UPDATE_PUBLIC_KEY_PEM', None)
    else:
        global_var._user_config['UPDATE_PUBLIC_KEY_PEM'] = saved_key
    if saved_iv is None:
        global_var._user_config.pop('UPDATE_CHECK_INTERVAL', None)
    else:
        global_var._user_config['UPDATE_CHECK_INTERVAL'] = saved_iv
finally:
    shutil.rmtree(iso, ignore_errors=True)

print(f"\n==== 发布签名联动测试 共 {len(results)} 项，通过 {sum(1 for _, c in results if c)}，失败 {sum(1 for _, c in results if not c)} ====")
sys.exit(0 if all(c for _, c in results) else 1)
