# -*- coding: utf-8 -*-
"""FlaskToolkit HTTPS 自签名证书生成工具（v4.5.0）

使用系统 openssl 生成自签名证书/私钥对（默认 RSA 2048，输出 data/certs/）。
不引入 cryptography 等第三方依赖；证书生成后通过 SSL_CERT_FILE / SSL_KEY_FILE 配置启用 HTTPS
（配置项可用 tools/config.py 管理，或手动写入 data/user_config.json）。

用法：
  python tools/gen_cert.py                    # 生成默认自签名证书（CN=localhost，SAN 含 localhost/127.0.0.1）
  python tools/gen_cert.py --cn myserver      # 指定通用名称
  python tools/gen_cert.py --san IP:192.168.1.10 --san DNS:myserver.local   # 追加 SAN（局域网访问）
  python tools/gen_cert.py --days 3650 --key-size 4096
  python tools/gen_cert.py --out D:/certs     # 自定义输出目录（默认 data/certs）

成功退出码：0；openssl 不可用或参数错误：非 0。
"""
import argparse
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import global_var

DEFAULT_OUT_DIR = os.path.join(global_var.BASE_DIR, 'data', 'certs')
DEFAULT_CN = 'localhost'
DEFAULT_DAYS = 3650
DEFAULT_KEY_SIZE = 2048
# 默认 SAN：本机回环 + 局域网可用主机名（可按需通过 --san 扩展）
DEFAULT_SAN = ['DNS:localhost', 'IP:127.0.0.1']

# 常见 openssl 路径（Windows Git Bash / 系统 PATH / 常见安装位置）
_OPENSSL_CANDIDATES = [
    'openssl',
    r'C:\Program Files\Git\usr\bin\openssl.exe',
    r'C:\Program Files\Git\mingw64\bin\openssl.exe',
    r'C:\Program Files\OpenSSL-Win64\bin\openssl.exe',
    '/usr/bin/openssl',
]


def find_openssl() -> str:
    """定位可用的 openssl 可执行文件；找不到返回空字符串"""
    found = shutil.which('openssl')
    if found:
        return found
    for cand in _OPENSSL_CANDIDATES[1:]:
        if os.path.isfile(cand):
            return cand
    return ''


def gen_cert(out_dir: str, cn: str, days: int, key_size: int, san: list) -> str:
    """调用 openssl 生成自签名证书，返回证书文件路径"""
    openssl = find_openssl()
    if not openssl:
        raise RuntimeError(
            "未找到 openssl。请安装 OpenSSL 并加入 PATH（Windows 可安装 Git for Windows 自带，"
            "或访问 https://slproweb.com/products/Win32OpenSSL.html），或用已配置的证书替代。")

    os.makedirs(out_dir, exist_ok=True)
    cert_path = os.path.join(out_dir, 'cert.pem')
    key_path = os.path.join(out_dir, 'key.pem')
    subj = f"/CN={cn}"
    cmd = [
        openssl, 'req', '-x509', '-newkey', f'rsa:{key_size}',
        '-keyout', key_path, '-out', cert_path,
        '-days', str(days), '-nodes', '-subj', subj,
    ]
    # 合并默认 SAN 与用户追加项（去重），单条 subjectAltName 逗号分隔（openssl 3.x 不支持重复扩展名）
    final_san = list(dict.fromkeys(DEFAULT_SAN + san))
    cmd += ['-addext', 'subjectAltName=' + ','.join(final_san)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"openssl 生成证书失败（exit={result.returncode}）：{result.stderr.strip()}")
    return cert_path


def main() -> int:
    parser = argparse.ArgumentParser(description='生成 FlaskToolkit HTTPS 自签名证书')
    parser.add_argument('--out', default=DEFAULT_OUT_DIR, help=f'输出目录（默认 {DEFAULT_OUT_DIR}）')
    parser.add_argument('--cn', default=DEFAULT_CN, help=f'证书通用名称 CN（默认 {DEFAULT_CN}）')
    parser.add_argument('--days', type=int, default=DEFAULT_DAYS, help=f'有效期天数（默认 {DEFAULT_DAYS}）')
    parser.add_argument('--key-size', type=int, default=DEFAULT_KEY_SIZE, help=f'RSA 密钥位数（默认 {DEFAULT_KEY_SIZE}）')
    parser.add_argument('--san', action='append', default=[],
                        help='追加 SAN 条目，如 IP:192.168.1.10 或 DNS:myserver.local（可多次指定）')
    args = parser.parse_args()

    if args.days <= 0:
        print(f"[gen_cert] 错误：--days 必须为正数，收到 {args.days}", file=sys.stderr)
        return 2

    try:
        cert_path = gen_cert(args.out, args.cn, args.days, args.key_size, args.san)
    except RuntimeError as e:
        print(f"[gen_cert] 错误：{e}", file=sys.stderr)
        return 1

    key_path = os.path.join(args.out, 'key.pem')
    print("[gen_cert] 自签名证书已生成：")
    print(f"  证书: {cert_path}")
    print(f"  私钥: {key_path}")
    print()
    print("启用 HTTPS 的两种方式：")
    print(f"  1) python tools/config.py set SSL_CERT_FILE {cert_path}")
    print(f"     python tools/config.py set SSL_KEY_FILE {key_path}")
    print("  2) 编辑 data/user_config.json 手动添加上述两项")
    print()
    print("注意事项：")
    print("  - 自签名证书仅供内部/局域网信任场景使用，浏览器会提示不受信任，需手动信任或导入证书。")
    print("  - 私钥 key.pem 属敏感文件，请勿提交到版本库；.gitignore 已默认忽略 data/certs/。")
    return 0


if __name__ == '__main__':
    sys.exit(main())
