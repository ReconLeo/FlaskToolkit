# -*- coding: utf-8 -*-
"""插件包完整性校验与可选签名（P2-4，方案C：哈希清单 + 可选非对称签名）

manifest.json 结构（位于包根目录）：
    {
      "schema_version": "1.0",
      "package_type": "backend" | "frontend",
      "files": {"相对路径": "sha256hex", ...},
      "signature": {"algorithm": "RSA-SHA256", "value": "base64", "signer": ""}  # 可选
    }

- 完整性：安装时对包内除 manifest.json 外的全部成员计算 sha256 与 manifest.files 比对，
  防篡改/损坏/zip slip 错位/加料（包内出现未列清单的文件也拒绝）。
- 签名（可选）：打包者用 RSA 私钥对 files 规范化摘要签名；框架配置公钥后安装时验证。
- 校验模式：global_var.PACKAGE_INTEGRITY_MODE（strict/warn/off，默认 warn）
    - strict：缺 manifest 或校验失败 → 拒绝安装（强制所有包带清单）
    - warn：缺 manifest 仅告警放行（兼容旧包）；有 manifest 则严格校验
    - off：跳过全部校验
- 打包/签名/验证命令行工具见 tools/package.py
"""
import base64
import hashlib
import json
import logging
import zipfile

import global_var

logger = logging.getLogger('flask.app')

MANIFEST_FILE = 'manifest.json'
SCHEMA_VERSION = '1.0'
DEFAULT_ALGORITHM = 'RSA-SHA256'
INTEGRITY_MODES = ('strict', 'warn', 'off')


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_manifest(zf) -> dict | None:
    """读取包内 manifest.json；不存在返回 None，格式错误抛 ValueError"""
    names = [n.replace('\\', '/') for n in zf.namelist()]
    if MANIFEST_FILE not in names:
        return None
    try:
        m = json.loads(zf.read(MANIFEST_FILE).decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError(f"{MANIFEST_FILE} 格式错误（需为合法 JSON）")
    if not isinstance(m, dict):
        raise ValueError(f"{MANIFEST_FILE} 必须为 JSON 对象")
    return m


def _members_of(zf) -> list:
    names = [n.replace('\\', '/') for n in zf.namelist()]
    return [n for n in names if n != MANIFEST_FILE and not n.endswith('/')]


def verify_integrity(zf, manifest) -> tuple[bool, str]:
    """校验包内全部成员（除 manifest.json）的 sha256 与 manifest.files 一致。
    返回 (ok, message)。"""
    files = manifest.get('files')
    if not isinstance(files, dict):
        return False, f"{MANIFEST_FILE} 缺少 files 字段（哈希清单）"

    members = _members_of(zf)
    manifest_paths = set(files.keys())
    member_paths = set(members)

    extra = sorted(member_paths - manifest_paths)
    if extra:
        return False, f"完整性校验失败：包内存在未在清单中的文件: {', '.join(extra[:5])}"
    missing = sorted(manifest_paths - member_paths)
    if missing:
        return False, f"完整性校验失败：清单中缺失文件: {', '.join(missing[:5])}"

    for path in members:
        expected = files.get(path)
        if not expected:
            continue
        try:
            actual = sha256_hex(zf.read(path))
        except Exception as e:
            return False, f"完整性校验失败：读取 {path} 出错: {e}"
        if actual != expected:
            return False, f"完整性校验失败：{path} 哈希不一致（内容可能被篡改或损坏）"

    return True, f"完整性校验通过（{len(members)} 个文件）"


def _signing_data(manifest: dict) -> bytes:
    """签名对象 = 除 signature 外字段的规范化 JSON（紧凑、按键排序）"""
    payload = {k: v for k, v in manifest.items() if k != 'signature'}
    return json.dumps(payload, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False).encode('utf-8')


def sign_manifest(manifest: dict, private_key_pem_path: str, signer: str = '') -> dict:
    """用 RSA 私钥对 manifest 摘要签名，返回带 signature 的 manifest 副本"""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    with open(private_key_pem_path, 'rb') as f:
        key = serialization.load_pem_private_key(f.read(), password=None)
    sig = key.sign(_signing_data(manifest), padding.PKCS1v15(), hashes.SHA256())
    out = dict(manifest)
    out['signature'] = {
        'algorithm': DEFAULT_ALGORITHM,
        'value': base64.b64encode(sig).decode('ascii'),
        'signer': signer,
    }
    return out


def verify_signature(manifest: dict, public_key_pem_path: str) -> tuple[bool, str]:
    """用公钥验证 manifest.signature；无 signature 返回 (False, '未签名')"""
    sig = manifest.get('signature')
    if not sig:
        return False, '未签名'
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        with open(public_key_pem_path, 'rb') as f:
            pub = serialization.load_pem_public_key(f.read())
        pub.verify(base64.b64decode(sig['value']), _signing_data(manifest),
                   padding.PKCS1v15(), hashes.SHA256())
        return True, '签名有效'
    except Exception as e:
        return False, f'签名验证失败: {e}'


def make_manifest(zf, package_type: str) -> dict:
    """为包生成 manifest（CLI 打包用）：列出全部成员哈希"""
    files = {}
    for path in sorted(_members_of(zf)):
        files[path] = sha256_hex(zf.read(path))
    return {
        'schema_version': SCHEMA_VERSION,
        'package_type': package_type,
        'files': files,
    }


def verify_package(zip_path: str, package_type: str = '') -> dict:
    """上传/更新时对插件包做完整性 + 可选签名校验（统一入口）。

    返回:
      {'ok': bool, 'mode': str, 'signed': bool, 'signature_ok': bool|None,
       'message': str, 'warn_only': bool}
    - ok=False 且 warn_only=False → 调用方应拒绝安装
    - warn_only=True → 调用方放行但提示警告（缺清单时的 warn 模式）
    """
    mode = getattr(global_var, 'PACKAGE_INTEGRITY_MODE', 'warn')
    if mode not in INTEGRITY_MODES:
        mode = 'warn'
    if mode == 'off':
        return {'ok': True, 'mode': mode, 'signed': False, 'signature_ok': None,
                'message': '完整性校验已关闭', 'warn_only': False}

    try:
        zf = zipfile.ZipFile(zip_path, 'r')
    except zipfile.BadZipFile:
        return {'ok': False, 'mode': mode, 'signed': False, 'signature_ok': None,
                'message': '无效的 zip 文件', 'warn_only': False}

    with zf:
        try:
            manifest = read_manifest(zf)
        except ValueError as e:
            return {'ok': False, 'mode': mode, 'signed': False, 'signature_ok': None,
                    'message': str(e), 'warn_only': mode == 'warn'}

        if manifest is None:
            if mode == 'strict':
                return {'ok': False, 'mode': mode, 'signed': False, 'signature_ok': None,
                        'message': f'缺少 {MANIFEST_FILE} 完整性清单（strict 模式拒绝安装，'
                                   '请使用 tools/package.py 重新打包）',
                        'warn_only': False}
            return {'ok': True, 'mode': mode, 'signed': False, 'signature_ok': None,
                    'message': f'缺少 {MANIFEST_FILE}（warn 模式放行，建议用打包工具生成清单）',
                    'warn_only': True}

        ok, msg = verify_integrity(zf, manifest)
        if not ok:
            return {'ok': False, 'mode': mode, 'signed': False, 'signature_ok': None,
                    'message': msg, 'warn_only': False}

        signed = bool(manifest.get('signature'))
        pub = getattr(global_var, 'PLUGIN_PUBLIC_KEY_PEM', '')
        sig_ok = None
        sig_msg = ''
        if signed:
            if pub:
                sig_ok, sig_msg = verify_signature(manifest, pub)
                if not sig_ok:
                    return {'ok': False, 'mode': mode, 'signed': True, 'signature_ok': False,
                            'message': sig_msg, 'warn_only': False}
            else:
                sig_msg = '未配置公钥，跳过签名验证'
        if sig_ok:
            sig_msg = '签名有效'
        message = msg + (f'；{sig_msg}' if sig_msg else '')
        return {'ok': True, 'mode': mode, 'signed': signed, 'signature_ok': sig_ok,
                'message': message, 'warn_only': False}
