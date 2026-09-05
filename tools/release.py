# -*- coding: utf-8 -*-
"""
框架发布工具链（v4.8.0）：版本号同步 / 更新包构建 / changelog 生成与签名

用法：
  1) 版本号同步（三处 + SYSTEM_VERSION_LABEL）：
     python tools/release.py --bump-version 4.8.0
  2) 构建更新包 + 写 changelog.json：
     python tools/release.py --build --version 4.8.0 \
         --changes "版本检查与更新机制（F1/F4）" --changes "..." \
         --download-url "https://github.com/ReconLeo/FlaskToolkit/releases/download/v4.8.0/FlaskToolkit-v4.8.0-runtime.zip" \
         [--full] [--include /path/src:rel/dest ...] [--sign private.pem] [--out dist]

更新包形态（审计意见）：默认精简运行包；--full 全量包（含 tests/documents/examples）；--include 叠加企业定制附加项。

发布流程：--bump-version → 全量回归 → --build（--sign 可选）→ git 提交 + GitHub Release 上传 zip + push changelog.json。
"""
import argparse
import hashlib
import io
import json
import os
import re
import sys
import time
import zipfile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# 与 tools/update.py 保持一致的用户数据路径（打包/更新保留语义统一）
from tools.update import USER_DATA_PATHS, path_is_user_data

# 精简包顶层白名单
# locales/ 为框架内置 i18n 语言包（v4.9.0），精简运行包必须包含（否则更新后界面翻译缺失）
RUNTIME_TOP = ['app.py', 'global_var.py', 'requirements.txt', 'core', 'routes', 'plugins', 'templates', 'static', 'locales']
# 内置插件白名单（用户插件不入精简包；plugins/configs|data|temp 为运行时数据不入包）
RUNTIME_PLUGIN_FILES = {'__init__.py', 'base_plugin.py', 'auth.py', 'user_manage.py'}
# templates 下排除的用户内容子目录（插件模板/前端工具模板）
RUNTIME_TEMPLATE_EXCLUDE = {'plugins', 'frontend_tools'}

# changelog 签名覆盖字段（与 core/update_checker.SIGNED_FIELDS 对齐）
SIGNED_FIELDS = ('latest_version', 'published_at', 'download_url', 'sha256', 'changes')


def log(msg):
    print(f"[release] {msg}", flush=True)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def replace_first(path, old, new):
    with io.open(path, encoding='utf-8', newline='') as f:
        c = f.read()
    assert c.count(old) >= 1, f'{path}: 锚点未找到: {old[:60]!r}'
    c = c.replace(old, new, 1)
    with io.open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(c)


# ------------------------------ bump 版本号 ------------------------------

def cmd_bump(args):
    ver = args.version
    vlabel = 'v' + ver
    # global_var.py：FRAMEWORK_VERSION + SYSTEM_VERSION_LABEL 默认值
    replace_first(os.path.join(BASE_DIR, 'global_var.py'),
                  f'FRAMEWORK_VERSION = "{ver}"',
                  f'FRAMEWORK_VERSION = "{ver}"')
    replace_first(os.path.join(BASE_DIR, 'global_var.py'),
                  f"'SYSTEM_VERSION_LABEL': {{'default': '{vlabel}'",
                  f"'SYSTEM_VERSION_LABEL': {{'default': '{vlabel}'")
    # tests/test_admin_api.py：framework_version 断言
    replace_first(os.path.join(BASE_DIR, 'tests', 'test_admin_api.py'),
                  f"== '{ver}'", f"== '{ver}'")
    # README 双版徽章
    for p in ('README.md', 'README.zh-CN.md'):
        path = os.path.join(BASE_DIR, p)
        with io.open(path, encoding='utf-8', newline='') as f:
            c = f.read()
        c2 = re.sub(r'badge/version-[0-9.]+-blue', f'badge/version-{ver}-blue', c)
        assert c2 != c, f'{p}: 未找到 version 徽章'
        with io.open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(c2)
    log(f'版本号已同步: {ver}（global_var / test_admin_api / README 双版徽章）')
    log('提醒：还需手动更新开发规范版本段、Roadmap 版本表、README 特性条目与断言数。')
    return 0


# ------------------------------ 构建更新包 ------------------------------

def collect_runtime_files():
    """精简包文件清单（白名单 + 排除用户数据路径/缓存）"""
    files = []
    for top in RUNTIME_TOP:
        p = os.path.join(BASE_DIR, top)
        if os.path.isfile(p):
            files.append(top)
            continue
        if not os.path.isdir(p):
            log(f'警告: 精简清单条目缺失 {top}（跳过）')
            continue
        for root, dirs, fns in os.walk(p):
            rel_root = os.path.relpath(root, BASE_DIR).replace('\\', '/')
            dirs[:] = [d for d in dirs
                       if d != '__pycache__' and not path_is_user_data((rel_root + '/' + d).lstrip('/'))]
            for fn in fns:
                rel = (rel_root + '/' + fn).lstrip('/')
                if rel.endswith('.pyc'):
                    continue
                if top == 'plugins':
                    sub = rel[len('plugins/'):]
                    if '/' in sub or fn not in RUNTIME_PLUGIN_FILES:
                        continue  # 子目录/非内置插件跳过
                if top == 'templates':
                    first = rel.split('/')[1] if '/' in rel else ''
                    if first in RUNTIME_TEMPLATE_EXCLUDE:
                        continue
                files.append(rel)
    return sorted(set(files))


def collect_full_files():
    """全量包文件清单（全部仓库文件，排除 .git/用户数据/缓存）"""
    files = []
    for root, dirs, fns in os.walk(BASE_DIR):
        rel_root = os.path.relpath(root, BASE_DIR).replace('\\', '/')
        if rel_root == '.':
            rel_root = ''
        dirs[:] = [d for d in dirs
                   if d not in ('.git', '__pycache__', '.plugin_cache')
                   and not path_is_user_data((rel_root + '/' + d).lstrip('/'))]
        for fn in fns:
            rel = (rel_root + '/' + fn).lstrip('/')
            if rel.endswith('.pyc') or rel.startswith('releases/'):
                continue
            files.append(rel)
    return sorted(set(files))


def parse_includes(include_args):
    """--include src:dest 解析为 [(src_abs, dest_rel), ...]"""
    out = []
    for item in include_args or []:
        if ':' not in item:
            raise SystemExit(f'--include 格式应为 <src>:<dest>，收到: {item}')
        src, dest = item.split(':', 1)
        src = os.path.abspath(src)
        if not os.path.exists(src):
            raise SystemExit(f'--include 源不存在: {src}')
        dest = dest.replace('\\', '/').lstrip('/')
        out.append((src, dest))
    return out


def build_package(version, full=False, includes=None, out_dir=None):
    """构建更新包（含 manifest.json），返回 zip 路径"""
    files = collect_full_files() if full else collect_runtime_files()
    # 定制附加（企业自定义目录/文件）
    include_map = {}
    for src, dest in (includes or []):
        if os.path.isdir(src):
            for root, dirs, fns in os.walk(src):
                rel_root = os.path.relpath(root, src).replace('\\', '/')
                if rel_root == '.':
                    rel_root = ''
                for fn in fns:
                    rel = (rel_root + '/' + fn).lstrip('/')
                    include_map[dest + '/' + rel] = os.path.join(root, fn)
        else:
            include_map[dest] = src

    pkg_type = 'framework-full' if full else 'framework-custom' if includes else 'framework-runtime'
    out_dir = out_dir or os.path.join(BASE_DIR, 'releases')
    os.makedirs(out_dir, exist_ok=True)
    suffix = 'full' if full else 'runtime'
    out = os.path.join(out_dir, f'FlaskToolkit-{version}-{suffix}.zip')

    manifest_files = {}
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            if path_is_user_data(rel):
                continue
            src = os.path.join(BASE_DIR, rel)
            if not os.path.isfile(src):
                continue
            zf.write(src, arcname=rel)
            manifest_files[rel] = sha256_file(src)
        for dest, src in sorted(include_map.items()):
            if path_is_user_data(dest):
                log(f'跳过用户数据路径附加项: {dest}')
                continue
            zf.write(src, arcname=dest)
            manifest_files[dest] = sha256_file(src)
        manifest = {
            'schema_version': '1.0',
            'package_type': pkg_type,
            'version': version,
            'required_python': '3.10+',
            'files': manifest_files,
        }
        zf.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    log(f'构建完成: {out}（{len(manifest_files)} 个文件，type={pkg_type}）')
    return out


def write_changelog(version, changes, download_url, sha256, out_path=None, private_key=None):
    """写根目录 changelog.json（只存最新版本），可选签名"""
    changelog = {
        'latest_version': version,
        'published_at': time.strftime('%Y-%m-%d'),
        'download_url': download_url,
        'sha256': sha256,
        'changes': changes,
    }
    if private_key:
        sys.path.insert(0, BASE_DIR)
        from core.package_sign import sign_manifest
        signed = sign_manifest(changelog, private_key, signer='FlaskToolkit-release')
        changelog = signed
    out_path = out_path or os.path.join(BASE_DIR, 'changelog.json')
    with io.open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(changelog, f, ensure_ascii=False, indent=2)
    log(f'changelog 已写入: {out_path}（latest_version={version}）')
    return out_path


def cmd_build(args):
    if not args.version:
        raise SystemExit('--build 需要 --version <ver>')
    if not args.download_url:
        raise SystemExit('--build 需要 --download-url <url>（更新包下载地址）')
    includes = parse_includes(args.include or [])
    zip_path = build_package(args.version, full=args.full, includes=includes, out_dir=args.out)
    sha = sha256_file(zip_path)
    write_changelog(args.version, args.changes or [], args.download_url, sha,
                    private_key=args.sign)
    log(f'包 sha256: {sha}')
    log('发布流程：git 提交 + GitHub Release 上传 zip + push changelog.json。')
    return 0


def main():
    ap = argparse.ArgumentParser(description='FlaskToolkit 发布工具链')
    sub = ap.add_subparsers(dest='cmd', required=True)

    b = sub.add_parser('bump', help='同步版本号（三处 + SYSTEM_VERSION_LABEL + README 徽章）')
    b.add_argument('--version', required=True, help='新版本号，如 4.8.0')
    b.set_defaults(func=cmd_bump)

    build = sub.add_parser('build', help='构建更新包 + 写 changelog.json')
    build.add_argument('--version', required=True, help='版本号')
    build.add_argument('--changes', action='append', default=[], help='变更条目（可多次）')
    build.add_argument('--download-url', required=True, help='更新包下载地址')
    build.add_argument('--full', action='store_true', help='构建全量包（默认精简运行包）')
    build.add_argument('--include', action='append', default=[], help='定制附加 <src>:<dest>（可多次）')
    build.add_argument('--sign', default=None, help='RSA 私钥 PEM 路径（对 changelog 签名）')
    build.add_argument('--out', default=None, help='产物目录（默认 releases/）')
    build.set_defaults(func=cmd_build)

    args = ap.parse_args()
    sys.exit(args.func(args) or 0)


if __name__ == '__main__':
    main()
