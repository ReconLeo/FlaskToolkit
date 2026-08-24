# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""插件包完整性校验与签名专项测试（P2-4 方案C）

覆盖：
- 模块层：sha256 / make_manifest / verify_integrity（正常、篡改、加料、缺文件）
- 签名：sign_manifest + verify_signature（正确公钥通过 / 错误公钥失败 / 篡改后失败）
- verify_package 模式行为：warn 缺清单放行 / strict 缺清单拒绝 / off 跳过 /
  有清单严格校验（不匹配即拒，与模式无关）/ 签名强校验（配公钥后签名失败拒绝）
- 路由集成：前端工具上传（有清单通过、篡改拒绝、warn 缺清单放行、strict 缺清单拒绝）

运行：python test_package_sign.py
"""
import io
import json
import os
import shutil
import sys
import tempfile
import zipfile

REAL_BASE = _PROJECT_ROOT
sys.path.insert(0, REAL_BASE)

import global_var
from core import package_sign as ps

results = []

def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")


def make_zip(members: dict, manifest=None) -> bytes:
    """members: {path: bytes}；manifest: 传入 dict 则写入 manifest.json，None 则不写"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path, data in members.items():
            zf.writestr(path, data)
        if manifest is not None:
            zf.writestr(ps.MANIFEST_FILE, json.dumps(manifest, ensure_ascii=False))
    buf.seek(0)
    return buf.read()


def write_tmp(data: bytes) -> str:
    p = os.path.join(tempfile.mkdtemp(prefix='ftk_pk_'), 'pkg.zip')
    with open(p, 'wb') as f:
        f.write(data)
    return p


def gen_keypair(tmpdir):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = os.path.join(tmpdir, 'private.pem')
    pub = os.path.join(tmpdir, 'public.pem')
    open(priv, 'wb').write(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()))
    open(pub, 'wb').write(key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    return priv, pub


def main():
    _tmp = tempfile.mkdtemp(prefix='ftk_pk_')
    priv, pub = gen_keypair(_tmp)
    _saved_mode = getattr(global_var, 'PACKAGE_INTEGRITY_MODE', 'warn')
    _saved_key = getattr(global_var, 'PLUGIN_PUBLIC_KEY_PEM', '')

    try:
        # ---------- 模块层：sha256 ----------
        check('sha256_hex 正确', ps.sha256_hex(b'abc') ==
              'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad', '')

        # ---------- make_manifest + verify_integrity ----------
        members = {'config.json': b'{}', 'demo_tool.html': b'<html></html>',
                   'static/js/a.js': b'console.log(1)'}
        zdata = make_zip(members)
        with zipfile.ZipFile(io.BytesIO(zdata), 'r') as zf:
            man = ps.make_manifest(zf, 'frontend')
        check('make_manifest 含全部成员', set(man['files'].keys()) == set(members.keys()),
              f"{list(man['files'].keys())}")

        ok_zip = make_zip(members, man)
        with zipfile.ZipFile(io.BytesIO(ok_zip), 'r') as zf:
            ok, msg = ps.verify_integrity(zf, man)
        check('完整性：正常包通过', ok, msg)

        # 篡改：改 html 内容（manifest 不变）
        tampered = {k: (b'<html>HACK</html>' if k == 'demo_tool.html' else v)
                    for k, v in members.items()}
        tz = make_zip(tampered, man)
        with zipfile.ZipFile(io.BytesIO(tz), 'r') as zf:
            ok, msg = ps.verify_integrity(zf, man)
        check('完整性：篡改文件失败', not ok and 'demo_tool.html' in msg, msg)

        # 加料：包内多出未列清单文件
        add = dict(members); add['static/js/evil.js'] = b'evil'
        az = make_zip(add, man)
        with zipfile.ZipFile(io.BytesIO(az), 'r') as zf:
            ok, msg = ps.verify_integrity(zf, man)
        check('完整性：加料文件失败', not ok and '未在清单' in msg, msg)

        # 删文件：清单有但包内缺失
        cut = {k: v for k, v in members.items() if k != 'static/js/a.js'}
        cz = make_zip(cut, man)
        with zipfile.ZipFile(io.BytesIO(cz), 'r') as zf:
            ok, msg = ps.verify_integrity(zf, man)
        check('完整性：缺失文件失败', not ok and '缺失' in msg, msg)

        # ---------- 签名 ----------
        signed_man = ps.sign_manifest(man, priv, signer='测试')
        check('sign_manifest 生成 signature', 'signature' in signed_man
              and signed_man['signature']['algorithm'] == 'RSA-SHA256', '')
        vok, vmsg = ps.verify_signature(signed_man, pub)
        check('签名：正确公钥通过', vok, vmsg)
        # 错误公钥
        wrong = _tmp.replace('ftk_pk_', 'ftk_pk2_') + '_wrong.pem'
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        wk = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        open(wrong, 'wb').write(wk.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
        vok, vmsg = ps.verify_signature(signed_man, wrong)
        check('签名：错误公钥失败', not vok, vmsg)
        # 篡改 manifest（改 files 后验签）
        tampered_man = dict(signed_man)
        tampered_man['files'] = dict(tampered_man['files'])
        tampered_man['files']['static/js/a.js'] = 'x' * 64
        vok, vmsg = ps.verify_signature(tampered_man, pub)
        check('签名：篡改清单后失败', not vok, vmsg)

        # ---------- verify_package 模式行为 ----------
        pkg_ok = write_tmp(ok_zip)                      # 带清单正常
        pkg_old = write_tmp(make_zip(members))           # 无清单
        pkg_bad = write_tmp(tz)                          # 带清单但被篡改
        pkg_signed = write_tmp(make_zip(members, signed_man))  # 带签名

        # warn 模式：缺清单放行（warn_only）
        global_var.PACKAGE_INTEGRITY_MODE = 'warn'
        r = ps.verify_package(pkg_old, 'frontend')
        check('warn：缺清单放行 warn_only', r['ok'] and r['warn_only'], f"{r}")
        r = ps.verify_package(pkg_ok, 'frontend')
        check('warn：有清单正常通过', r['ok'] and not r['warn_only'], f"{r}")
        r = ps.verify_package(pkg_bad, 'frontend')
        check('warn：有清单但篡改仍拒绝', not r['ok'], f"{r}")

        # strict 模式：缺清单拒绝
        global_var.PACKAGE_INTEGRITY_MODE = 'strict'
        r = ps.verify_package(pkg_old, 'frontend')
        check('strict：缺清单拒绝', not r['ok'] and '缺少' in r['message'], f"{r}")
        r = ps.verify_package(pkg_ok, 'frontend')
        check('strict：有清单通过', r['ok'], f"{r}")

        # off 模式：跳过
        global_var.PACKAGE_INTEGRITY_MODE = 'off'
        r = ps.verify_package(pkg_bad, 'frontend')
        check('off：跳过校验', r['ok'] and '关闭' in r['message'], f"{r}")

        # 签名强校验：配公钥后签名包通过 / 篡改包拒绝
        global_var.PACKAGE_INTEGRITY_MODE = 'strict'
        global_var.PLUGIN_PUBLIC_KEY_PEM = pub
        r = ps.verify_package(pkg_signed, 'frontend')
        check('签名包+公钥：通过且 signature_ok', r['ok'] and r['signed'] and r['signature_ok'] is True,
              f"{r['message']}")
        # 无签名包 + 已配公钥：仍通过（完整性已足，仅提示未签名）
        r = ps.verify_package(pkg_ok, 'frontend')
        check('无签名包+公钥：通过（完整性足够）', r['ok'] and not r['signed'], f"{r}")

        # ---------- 路由集成（隔离环境前端工具上传） ----------
        # 注意：config.json 必须含 name/version/category 且入口 html = <name>.html，否则在完整性校验后
        # 会被必填字段校验拦截；断言用 json 解析（jsonify ensure_ascii 会把中文转成 \uXXXX）
        tool_cfg = json.dumps({"name": "demo_tool", "version": "1.0.0", "category": "测试"},
                              ensure_ascii=False).encode('utf-8')
        tool_members = {'config.json': tool_cfg, 'demo_tool.html': b'<html>tool</html>',
                        'static/js/a.js': b'console.log(1)'}
        _tbuf = io.BytesIO()
        with zipfile.ZipFile(_tbuf, 'w') as zf:
            for _p, _d in tool_members.items():
                zf.writestr(_p, _d)
        _tbuf.seek(0)
        with zipfile.ZipFile(io.BytesIO(_tbuf.read()), 'r') as zf:
            _tman = ps.make_manifest(zf, 'frontend')
        tool_ok_zip = make_zip(tool_members, _tman)
        tool_tampered = {k: (b'<html>HACK</html>' if k == 'demo_tool.html' else v)
                         for k, v in tool_members.items()}
        tool_bad_zip = make_zip(tool_tampered, _tman)
        tool_old_zip = make_zip(tool_members)

        isolated = tempfile.mkdtemp(prefix='ftk_pk_route_')
        os.makedirs(os.path.join(isolated, 'plugins'))
        os.makedirs(os.path.join(isolated, 'temp'))
        os.makedirs(os.path.join(isolated, 'templates', 'frontend_tools'))
        os.makedirs(os.path.join(isolated, 'data'))
        shutil.copy(os.path.join(REAL_BASE, 'plugins', '__init__.py'), os.path.join(isolated, 'plugins'))
        shutil.copy(os.path.join(REAL_BASE, 'plugins', 'base_plugin.py'), os.path.join(isolated, 'plugins'))
        sys.path.insert(0, isolated)
        _saved_paths = {}
        for a, v in (('BASE_DIR', isolated), ('UPLOAD_TEMP_DIR', os.path.join(isolated, 'temp')),
                     ('FRONTEND_TEMPLATE_DIR', os.path.join(isolated, 'templates', 'frontend_tools')),
                     ('FRONTEND_CONFIG_FILE', os.path.join(isolated, 'frontend_tools.json')),
                     ('STATS_FILE', os.path.join(isolated, 'data', 'stats.json'))):
            _saved_paths[a] = getattr(global_var, a, None)
            setattr(global_var, a, v)
        import app as appmod
        from core.plugin_loader import load_plugins
        app = appmod.app
        app.config["TESTING"] = True
        from jinja2 import ChoiceLoader, FileSystemLoader
        app.jinja_env.loader = ChoiceLoader([
            FileSystemLoader(os.path.join(isolated, 'templates')),
            FileSystemLoader(os.path.join(REAL_BASE, 'templates')),
        ])
        load_plugins()
        global_var.frontend_tools = []

        def upload(zip_bytes, name='tool'):
            client = app.test_client()
            return client.post('/api/admin/frontend/upload',
                               data={'file': (io.BytesIO(zip_bytes), f'{name}.zip', 'application/zip')},
                               content_type='multipart/form-data')

        global_var.PACKAGE_INTEGRITY_MODE = 'strict'
        r = upload(tool_ok_zip, 'tool_ok')
        check('路由：strict 有清单包上传 200', r.status_code == 200, f"status={r.status_code} {r.get_data(as_text=True)[:80]}")
        r = upload(tool_bad_zip, 'tampered')
        _body = json.loads(r.get_data(as_text=True))
        check('路由：篡改包上传 400（完整性失败）',
              r.status_code == 400 and '完整性' in (_body.get('message') or ''),
              f"status={r.status_code} {r.get_data(as_text=True)[:80]}")
        r = upload(tool_old_zip, 'old')
        _body = json.loads(r.get_data(as_text=True))
        check('路由：strict 缺清单包上传 400',
              r.status_code == 400 and '缺少' in (_body.get('message') or ''),
              f"status={r.status_code} {r.get_data(as_text=True)[:80]}")
        # 注意：前一个用例已上传 demo_tool，这里用不同 name 的工具包避免同名冲突
        tool_old2_cfg = json.dumps({"name": "demo_tool2", "version": "1.0.0", "category": "测试"},
                                   ensure_ascii=False).encode('utf-8')
        tool_old2 = {'config.json': tool_old2_cfg, 'demo_tool2.html': b'<html>2</html>'}
        global_var.PACKAGE_INTEGRITY_MODE = 'warn'
        r = upload(make_zip(tool_old2), 'old2')
        check('路由：warn 缺清单包上传 200（放行）', r.status_code == 200,
              f"status={r.status_code} {r.get_data(as_text=True)[:80]}")

        # 清理隔离目录
        for a, v in _saved_paths.items():
            if v is None:
                try:
                    delattr(global_var, a)
                except AttributeError:
                    pass
            else:
                setattr(global_var, a, v)
        try:
            shutil.rmtree(isolated, ignore_errors=True)
        except Exception:
            pass

    finally:
        global_var.PACKAGE_INTEGRITY_MODE = _saved_mode
        global_var.PLUGIN_PUBLIC_KEY_PEM = _saved_key
        try:
            shutil.rmtree(_tmp, ignore_errors=True)
        except Exception:
            pass

    passed = sum(1 for _, c, _ in results if c)
    print(f"\n==== 完整性/签名专项测试 共 {len(results)} 项，通过 {passed}，失败 {len(results)-passed} ====")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == '__main__':
    main()
