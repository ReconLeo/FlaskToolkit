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
import hashlib
import zipfile

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

# ==================== B2: update_from_feed 一键更新闭环（v4.21） ====================
# 覆盖：前置拒绝分支（未声明源/已最新/拉取失败/缺 download_url）→
# 下载 + sha256 校验 + 门禁委托（mock 门禁验证编排）→ 真实端到端（下载+sha256+门禁+加载）。
import core.plugin_admin as _pa

def _mk_update_feed(iso_dir, feed_name, zip_path, sha256, latest='9.9.9',
                    download_url=None, priv_=None):
    if priv_ is None:
        priv_ = priv_path  # 取当前模块级 priv_path（B2 段会重绑定到自身隔离密钥）
    _f = {'latest_version': latest, 'published_at': '2026-09-17',
          'download_url': (download_url if download_url is not None
                           else 'file:///' + zip_path.replace('\\', '/')),
          'sha256': sha256, 'changes': ['更新']}
    _f['signature'] = sign_manifest(_f, priv_, signer='test')['signature']
    fp = os.path.join(iso_dir, feed_name)
    with io.open(fp, 'w', encoding='utf-8') as f:
        json.dump(_f, f, ensure_ascii=False)
    return 'file:///' + fp.replace('\\', '/')

def _mk_package_zip(iso_dir, name='updemo', version='9.9.9'):
    zb = io.BytesIO()
    with zipfile.ZipFile(zb, 'w', zipfile.ZIP_STORED) as zf:
        zf.writestr('plugin.json', json.dumps({"name": name, "version": version,
            "permission": "user", "author": "T", "category": "测试",
            "description": "自动更新测试"}, ensure_ascii=False).encode('utf-8'))
        zf.writestr(name + '.py', '# -*- coding: utf-8 -*-\nfrom plugins.base_plugin import BasePlugin\n'
                    'class UpDemo(BasePlugin):\n    name="' + name + '"\n    version="' + version + '"\n    permission="user"\n')
    data = zb.getvalue()
    zp = os.path.join(iso_dir, f'{name}_{version}.zip')
    open(zp, 'wb').write(data)
    return zp, data

_iso2 = tempfile.mkdtemp(prefix='ftk_updfeed_')
# B2 用自己的 RSA 密钥（首段 iso 已在 finally 删除，模块级 priv_path 已失效）
from cryptography.hazmat.primitives.asymmetric import rsa as _rsa
from cryptography.hazmat.primitives import serialization as _ser
_priv2 = _rsa.generate_private_key(public_exponent=65537, key_size=2048)
_priv2_p = os.path.join(_iso2, 'priv2.pem'); _pub2_p = os.path.join(_iso2, 'pub2.pem')
open(_priv2_p, 'wb').write(_priv2.private_bytes(_ser.Encoding.PEM, _ser.PrivateFormat.PKCS8, _ser.NoEncryption()))
open(_pub2_p, 'wb').write(_priv2.public_key().public_bytes(_ser.Encoding.PEM, _ser.PublicFormat.SubjectPublicKeyInfo))
priv_path = _priv2_p  # 重绑定模块级名字，供 _mk_update_feed 回退使用
_sched = type('SchedStub', (), {'get_jobs': lambda self: [], 'get_job': lambda self, _: None,
                                'remove_job': lambda self, _: None, 'add_job': lambda self, **_k: None})()
try:
    _saved2 = (global_var.BASE_DIR, getattr(global_var, 'plugin_catalog', None),
               global_var._user_config.get('UPDATE_PUBLIC_KEY_PEM'),
               global_var._user_config.get('UPDATE_CHECK_INTERVAL'), global_var.scheduler)
    global_var.BASE_DIR = _iso2
    global_var._user_config['UPDATE_CHECK_INTERVAL'] = 0
    global_var._user_config['UPDATE_PUBLIC_KEY_PEM'] = _pub2_p
    global_var.scheduler = _sched

    # ---- A1. 未声明 update_feed ----
    global_var.plugin_catalog = [{'name': 'nofeed', 'version': '1.0.0'}]
    _a_ok, _a_msg, _ = pu.update_from_feed('nofeed', force=True)
    check('update_from_feed：未声明更新源拒绝', _a_ok is False and '未声明更新源' in _a_msg, repr(_a_msg))

    # ---- A2. 已是最新 ----
    global_var.plugin_catalog = [{'name': 'cur', 'version': '9.9.9',
        'update_feed': _mk_update_feed(_iso2, 'feed_cur.json', 'x.zip', '0' * 64, latest='9.9.9')}]
    _b_ok, _b_msg, _ = pu.update_from_feed('cur', force=True)
    check('update_from_feed：已是最新拒绝', _b_ok is False and '已是最新' in _b_msg, repr(_b_msg))

    # ---- A3. feed 拉取失败 ----
    global_var.plugin_catalog = [{'name': 'badfeed', 'version': '1.0.0',
        'update_feed': 'file:///' + os.path.join(_iso2, 'no_such_feed.json').replace('\\', '/')}]
    _c_ok, _c_msg, _ = pu.update_from_feed('badfeed', force=True)
    check('update_from_feed：feed 拉取失败提示', _c_ok is False and '更新源检查失败' in _c_msg, repr(_c_msg))

    # ---- A4. 缺 download_url ----
    global_var.plugin_catalog = [{'name': 'nodl', 'version': '1.0.0',
        'update_feed': _mk_update_feed(_iso2, 'feed_nodl.json', 'x.zip', '0' * 64,
                                       latest='9.9.9', download_url='')}]
    _d_ok, _d_msg, _ = pu.update_from_feed('nodl', force=True)
    check('update_from_feed：缺 download_url 拒绝', _d_ok is False and 'download_url' in _d_msg, repr(_d_msg))

    # ---- B. 下载 + sha256 校验 + 门禁委托（mock 门禁） ----
    _zp, _zdata = _mk_package_zip(_iso2)
    _good_sha = hashlib.sha256(_zdata).hexdigest()
    _feed_good = _mk_update_feed(_iso2, 'feed_good.json', _zp, _good_sha)
    global_var.plugin_catalog = [{'name': 'updemo', 'version': '1.0.0', 'update_feed': _feed_good}]
    _calls = []
    _removed = []
    _orig_remove = os.remove
    _orig_upd = _pa.update_from_package
    def _fake_update(zip_path, name, actor=None, source_label=None):
        _calls.append({'zip': zip_path, 'name': name, 'source': source_label})
        return True, f'插件 {name} 已更新', {}
    def _fake_remove(p):
        _removed.append(p)  # 记录清理调用（沙箱拦截真实 os.remove，故用记录型 fake 验证清理逻辑）
    os.remove = _fake_remove
    _pa.update_from_package = _fake_update
    try:
        _e_ok, _e_msg, _ = pu.update_from_feed('updemo', force=True)
    finally:
        _pa.update_from_package = _orig_upd
        os.remove = _orig_remove
    check('update_from_feed：下载+sha256通过并委托门禁', _e_ok is True and len(_calls) == 1, repr(_e_msg))
    check('update_from_feed：下载后用后清理已触发',
          len(_calls) == 1 and any(_r == _calls[0]['zip'] for _r in _removed),
          repr(_calls[0]['zip']) if _calls else '')

    # 错误 sha256 → 拒绝且不委托门禁
    _feed_bad = _mk_update_feed(_iso2, 'feed_badsha.json', _zp, 'f' * 64)
    global_var.plugin_catalog = [{'name': 'updemo', 'version': '1.0.0', 'update_feed': _feed_bad}]
    _calls2 = []
    _pa.update_from_package = _fake_update
    try:
        _f_ok, _f_msg, _ = pu.update_from_feed('updemo', force=True)
    finally:
        _pa.update_from_package = _orig_upd
    check('update_from_feed：sha256 不符拒绝且不委托门禁',
          _f_ok is False and 'sha256' in _f_msg and _calls2 == []
          and _pa.update_from_package is _orig_upd, repr(_f_msg))

    # ---- C. 真实端到端（下载 + sha256 + 门禁 + 加载） ----
    _zp2, _zdata2 = _mk_package_zip(_iso2)
    _sha2 = hashlib.sha256(_zdata2).hexdigest()
    _feed2 = _mk_update_feed(_iso2, 'feed_e2e.json', _zp2, _sha2)
    global_var.plugin_catalog = [{'name': 'updemo', 'version': '1.0.0', 'update_feed': _feed2}]
    sys.path.insert(0, _iso2)
    try:
        _g_ok, _g_msg, _ = pu.update_from_feed('updemo', force=True)
    finally:
        try:
            sys.path.remove(_iso2)
        except ValueError:
            pass
    check('update_from_feed：真实端到端更新成功', _g_ok is True, repr(_g_msg))
    check('update_from_feed：端到端已落盘目录化 plugins/updemo/updemo.py',
          os.path.exists(os.path.join(_iso2, 'plugins', 'updemo', 'updemo.py')))
    check('update_from_feed：描述落盘 plugins/updemo/updemo.json',
          os.path.exists(os.path.join(_iso2, 'plugins', 'updemo', 'updemo.json')))

    # 恢复全局状态
    global_var.BASE_DIR, global_var.plugin_catalog = _saved2[0], _saved2[1]
    global_var.scheduler = _saved2[4]
    global_var._user_config['UPDATE_PUBLIC_KEY_PEM'] = _saved2[2]
    if _saved2[3] is None:
        global_var._user_config.pop('UPDATE_CHECK_INTERVAL', None)
    else:
        global_var._user_config['UPDATE_CHECK_INTERVAL'] = _saved2[3]
finally:
    shutil.rmtree(_iso2, ignore_errors=True)

print(f"\n==== 插件更新源签名测试 共 {len(results)} 项，通过 {sum(1 for _, c in results if c)}，失败 {sum(1 for _, c in results if not c)} ====")
sys.exit(0 if all(c for _, c in results) else 1)
