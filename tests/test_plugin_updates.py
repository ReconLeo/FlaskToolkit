# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""插件级更新源签名测试（v4.15，第三方插件市场铺路）

覆盖 plugin_updates._verify_feed_signature 与 check_plugin_update：
- 未配置公钥 + 无签名 → 放行（返回更新信息）
- 配置 UPDATE_PUBLIC_KEY_PEM + 有效签名 → 通过
- 配置公钥 + 篡改签名 / 无签名 / 错误公钥 / 公钥文件不存在 → 拒绝
- 插件未声明 update_feed → 直接返回（无更新）
- 版本可用判断（is_newer：feed latest > 当前 version）

运行：python test_plugin_updates.py
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
from core import plugin_updates as pu
from core.update_checker import is_newer
from core.package_sign import sign_manifest

results = []

def check(name, cond, detail=''):
    results.append((name, cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

iso = tempfile.mkdtemp(prefix='ftk_pupd_')
try:
    # 生成 RSA 密钥对
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_path = os.path.join(iso, 'sig_private.pem')
    pub_path = os.path.join(iso, 'sig_public.pem')
    with open(priv_path, 'wb') as f:
        f.write(priv.private_bytes(serialization.Encoding.PEM,
                                   serialization.PrivateFormat.PKCS8,
                                   serialization.NoEncryption()))
    with open(pub_path, 'wb') as f:
        f.write(priv.public_key().public_bytes(serialization.Encoding.PEM,
                                               serialization.PublicFormat.SubjectPublicKeyInfo))

    def write_feed(path, latest='9.9.9', sign=True, priv=priv_path):
        feed = {'latest_version': latest, 'published_at': '2026-09-05',
                'download_url': 'http://x/z.zip', 'sha256': 'abcd', 'changes': ['更新']}
        if sign:
            s = sign_manifest(feed, priv, signer='test')
            feed['signature'] = s['signature']
        with io.open(path, 'w', encoding='utf-8') as f:
            json.dump(feed, f, ensure_ascii=False)

    # 保存全局状态
    saved_base = global_var.BASE_DIR
    saved_catalog = getattr(global_var, 'plugin_catalog', None)
    saved_key = global_var._user_config.get('UPDATE_PUBLIC_KEY_PEM')
    saved_iv = global_var._user_config.get('UPDATE_CHECK_INTERVAL')
    global_var.BASE_DIR = iso
    global_var._user_config['UPDATE_CHECK_INTERVAL'] = 0  # 每次 force 拉取

    def clear_cache():
        p = pu._cache_file()
        if os.path.exists(p):
            os.remove(p)

    def run_check(name, feed_path):
        """设置 plugin_catalog 中该插件的 update_feed 并检查更新。"""
        global_var.plugin_catalog = [
            {'name': name, 'version': '1.0.0',
             'update_feed': 'file:///' + feed_path.replace('\\', '/')}]
        clear_cache()
        return pu.check_plugin_update(name, force=True)

    # ---------- 1. 未配置公钥 + 无签名 → 放行 ----------
    f1 = os.path.join(iso, 'feed_nosig.json')
    write_feed(f1, sign=False)
    global_var._user_config['UPDATE_PUBLIC_KEY_PEM'] = ''
    r1 = run_check('demo_nosig', f1)
    check('插件更新：未配置公钥无签名放行', r1.get('available') is True and not r1.get('error'),
          repr(r1.get('latest_version')))
    check('插件更新：版本可用判断 is_newer', r1.get('available') is True and is_newer('9.9.9', '1.0.0'))

    # ---------- 2. 配置公钥 + 有效签名 → 通过 ----------
    f2 = os.path.join(iso, 'feed_ok.json')
    write_feed(f2, sign=True)
    global_var._user_config['UPDATE_PUBLIC_KEY_PEM'] = pub_path
    r2 = run_check('demo_ok', f2)
    check('插件更新：公钥+有效签名通过', r2.get('available') is True and not r2.get('error'),
          repr(r2.get('error')))

    # ---------- 3. 配置公钥 + 篡改签名 → 拒绝 ----------
    f3 = os.path.join(iso, 'feed_tamper.json')
    write_feed(f3, sign=True)
    _t = json.load(io.open(f3, encoding='utf-8'))
    _t['latest_version'] = '10.0.0'
    with io.open(f3, 'w', encoding='utf-8') as f:
        json.dump(_t, f, ensure_ascii=False)
    r3 = run_check('demo_tamper', f3)
    check('插件更新：公钥+篡改字段拒绝', r3.get('available') is False and bool(r3.get('error')),
          repr(r3.get('error')))

    # ---------- 4. 配置公钥 + 无签名 → 拒绝 ----------
    f4 = os.path.join(iso, 'feed_nosig2.json')
    write_feed(f4, sign=False)
    r4 = run_check('demo_nosig2', f4)
    check('插件更新：公钥+无签名拒绝', r4.get('available') is False and bool(r4.get('error')),
          repr(r4.get('error')))

    # ---------- 5. 配置公钥 + 错误公钥 → 拒绝 ----------
    _other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    wrong_pub = _other.public_key().public_bytes(serialization.Encoding.PEM,
                                                 serialization.PublicFormat.SubjectPublicKeyInfo)
    wrong_path = os.path.join(iso, 'wrong.pem')
    with open(wrong_path, 'wb') as f:
        f.write(wrong_pub)
    f5 = os.path.join(iso, 'feed_ok2.json')
    write_feed(f5, sign=True)
    global_var._user_config['UPDATE_PUBLIC_KEY_PEM'] = wrong_path
    r5 = run_check('demo_wrongkey', f5)
    check('插件更新：错误公钥拒绝', r5.get('available') is False and bool(r5.get('error')),
          repr(r5.get('error')))

    # ---------- 6. 公钥文件不存在 → 拒绝 ----------
    f6 = os.path.join(iso, 'feed_ok3.json')
    write_feed(f6, sign=True)
    global_var._user_config['UPDATE_PUBLIC_KEY_PEM'] = os.path.join(iso, 'nope.pem')
    r6 = run_check('demo_nokey', f6)
    check('插件更新：公钥文件不存在拒绝', r6.get('available') is False and bool(r6.get('error')),
          repr(r6.get('error')))

    # ---------- 7. 插件未声明 update_feed → 直接返回 ----------
    global_var.plugin_catalog = [{'name': 'demo_nofeed', 'version': '1.0.0'}]
    clear_cache()
    r7 = pu.check_plugin_update('demo_nofeed', force=True)
    check('插件更新：未声明更新源返回', r7.get('available') is False and r7.get('feed_url') == ''
          and not r7.get('error'))

    # 恢复全局状态
    global_var.BASE_DIR = saved_base
    if saved_catalog is None:
        global_var.plugin_catalog = []
    else:
        global_var.plugin_catalog = saved_catalog
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

print(f"\n==== 插件更新源签名测试 共 {len(results)} 项，通过 {sum(1 for _, c in results if c)}，失败 {sum(1 for _, c in results if not c)} ====")
sys.exit(0 if all(c for _, c in results) else 1)
