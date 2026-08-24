# -*- coding: utf-8 -*-
"""插件/前端工具打包签名命令行工具（P2-4 方案C）

用法：
  1. 生成密钥对（可选，仅需要签名时）
     python tools/package.py genkey -o private.pem --pub public.pem

  2. 打包目录为可安装包（自动生成 manifest.json 哈希清单）
     python tools/package.py pack ./demo_tool -o demo_tool.zip --type frontend
     python tools/package.py pack ./demo_plugin -o demo_plugin.zip --type backend --sign private.pem --signer "张三"

  3. 校验包（完整性 + 可选签名）
     python tools/package.py verify demo_tool.zip
     python tools/package.py verify demo_plugin.zip --public-key public.pem

  4. 查看包内容与清单状态
     python tools/package.py show demo_tool.zip

说明：
- manifest.json 记录包内全部成员（除清单自身）的 sha256；安装时框架逐文件比对，
  防篡改/损坏/zip slip 错位/加料。签名用 RSA-SHA256（需 cryptography 库）。
- 包结构（backend）：plugin.json + 主 .py + 可选 templates/static + manifest.json
- 包结构（frontend）：config.json + 入口 .html + 可选 static/ + manifest.json
"""
import argparse
import json
import os
import sys
import zipfile

# 允许直接运行（python tools/package.py ...）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.package_sign import (MANIFEST_FILE, read_manifest, make_manifest,
                               sha256_hex, sign_manifest, verify_package,
                               verify_signature)

DEFAULT_PUBLIC_KEY = 'tools/public.pem'


def cmd_genkey(args):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption())
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo)
    with open(args.private_key, 'wb') as f:
        f.write(private_pem)
    pub = args.public_key or (os.path.splitext(args.private_key)[0] + '_public.pem')
    with open(pub, 'wb') as f:
        f.write(public_pem)
    print(f"私钥已生成: {args.private_key}")
    print(f"公钥已生成: {pub}")
    print("提示：将公钥配置到框架 global_var.PLUGIN_PUBLIC_KEY_PEM 以启用签名验证；私钥务必妥善保管。")


def cmd_pack(args):
    src = os.path.abspath(args.src_dir)
    if not os.path.isdir(src):
        print(f"错误：源目录不存在: {src}", file=sys.stderr)
        sys.exit(1)

    # 按类型校验必备清单文件
    manifest_file = 'plugin.json' if args.type == 'backend' else 'config.json'
    if not os.path.exists(os.path.join(src, manifest_file)):
        print(f"错误：{args.type} 包缺少清单文件 {manifest_file}（应在源目录根下）", file=sys.stderr)
        sys.exit(1)

    # 收集全部文件（相对路径）
    file_list = []
    for root, dirs, files in os.walk(src):
        dirs.sort()
        for fn in sorted(files):
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, src).replace('\\', '/')
            file_list.append((rel, full))
    if not file_list:
        print("错误：源目录为空", file=sys.stderr)
        sys.exit(1)

    # 计算哈希 → manifest
    files_map = {rel: sha256_hex(open(full, 'rb').read()) for rel, full in file_list}
    manifest = {
        'schema_version': '1.0',
        'package_type': args.type,
        'files': files_map,
    }
    if args.sign:
        manifest = sign_manifest(manifest, args.sign, args.signer or '')

    # 写 zip（manifest.json 在前）
    out = os.path.abspath(args.output)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST_FILE, json.dumps(manifest, ensure_ascii=False, indent=2))
        for rel, full in file_list:
            zf.write(full, rel)

    signed = '（已签名）' if args.sign else '（未签名）'
    print(f"已打包: {out}  [{args.type} {signed}]")
    print(f"  文件数: {len(file_list)}  清单: {MANIFEST_FILE}")
    if args.sign:
        print(f"  签名者: {args.signer or '(未署名)'}  算法: {manifest['signature']['algorithm']}")
    print("提示：发布前可运行 verify 校验一遍；未签名包安装时仅做完整性校验。")


def cmd_verify(args):
    import global_var
    if args.public_key:
        global_var.PLUGIN_PUBLIC_KEY_PEM = args.public_key
    res = verify_package(args.package, args.type or '')
    print(f"[{'通过' if res['ok'] else '失败'}] {res['message']}  (mode={res['mode']})")
    if res.get('signed'):
        print(f"  签名: {'有效' if res.get('signature_ok') else '无效/未验证'} "
              f"({'已配置公钥验证' if args.public_key else '未配置公钥'})")
    sys.exit(0 if res['ok'] else 1)


def cmd_show(args):
    try:
        zf = zipfile.ZipFile(args.package, 'r')
    except zipfile.BadZipFile:
        print("错误：无效的 zip 文件", file=sys.stderr)
        sys.exit(1)
    with zf:
        names = [n.replace('\\', '/') for n in zf.namelist()]
        print(f"包: {args.package}  成员 {len([n for n in names if not n.endswith('/')])} 个")
        print("成员清单:")
        for n in names:
            if not n.endswith('/'):
                print(f"  {n}")
        m = read_manifest(zf)
        if m is None:
            print(f"⚠ 缺少 {MANIFEST_FILE}（未打包清单，安装时 warn 模式放行 / strict 模式拒绝）")
        else:
            print(f"\n清单: schema={m.get('schema_version')} type={m.get('package_type')} "
                  f"files={len(m.get('files', {}))}")
            if m.get('signature'):
                s = m['signature']
                print(f"签名: {s.get('algorithm')}  签名者: {s.get('signer') or '(未署名)'}")
            else:
                print("签名: 无（未签名）")


def main():
    ap = argparse.ArgumentParser(description='FlaskToolkit 插件/前端工具打包签名工具')
    sub = ap.add_subparsers(dest='cmd', required=True)

    g = sub.add_parser('genkey', help='生成 RSA-2048 密钥对')
    g.add_argument('-o', '--private-key', required=True, help='私钥输出路径 (.pem)')
    g.add_argument('--pub', dest='public_key', help='公钥输出路径（默认同目录 _public.pem）')
    g.set_defaults(func=cmd_genkey)

    p = sub.add_parser('pack', help='打包目录为可安装包（生成 manifest.json）')
    p.add_argument('src_dir', help='源目录（backend: 含 plugin.json；frontend: 含 config.json）')
    p.add_argument('-o', '--output', required=True, help='输出 .zip 路径')
    p.add_argument('--type', choices=['backend', 'frontend'], default='frontend',
                   help='包类型（默认 frontend）')
    p.add_argument('--sign', metavar='PRIVATE_KEY', help='用该私钥对清单签名（需先 genkey）')
    p.add_argument('--signer', default='', help='签名者署名（随签名记录）')
    p.set_defaults(func=cmd_pack)

    v = sub.add_parser('verify', help='校验包完整性（+可选签名）')
    v.add_argument('package', help='包路径 .zip')
    v.add_argument('--type', choices=['backend', 'frontend'], default='', help='包类型（可选）')
    v.add_argument('--public-key', help='公钥 PEM 路径（校验签名用）')
    v.set_defaults(func=cmd_verify)

    s = sub.add_parser('show', help='查看包内容与清单状态')
    s.add_argument('package', help='包路径 .zip')
    s.set_defaults(func=cmd_show)

    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
