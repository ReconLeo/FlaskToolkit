# -*- coding: utf-8 -*-
"""
版本更新脚本（v4.8.0，F4）：检查 / 备份 / 应用 / 回滚框架更新

双后端自动探测：
- git 后端：项目目录是 git 仓库（默认）：git fetch → stash → reset --hard origin/main → pip install → selfcheck
- archive 后端（非 Git，企业内网主路径）：读 changelog.json → 下载 zip → 校验 → 备份 → 替换（跳过用户数据路径）→ selfcheck

用法：
  python tools/update.py --check [--force] [--json]
  python tools/update.py --backup [--tag xxx]          # 备份框架文件 + 用户配置
  python tools/update.py --apply [--dry-run] [--backend git|archive] [--feed-url URL]
  python tools/update.py --rollback [--backup-file xxx]
  python tools/update.py --selfcheck                    # 单独跑启动自检

设计要点：
- 用户数据路径清单（USER_DATA_PATHS）单处定义，git 后端（gitignore 语义）与 archive 后端共用。
- 更新前 selfcheck 记录当前完整性；更新后 selfcheck 验证；失败自动回滚（archive 后端）。
- 非 Git 更新本质是执行发布者代码：sha256 必选比对（changelog 内），配置 UPDATE_PUBLIC_KEY_PEM 后强制验签。
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

# 项目根（本文件位于 tools/ 下）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 用户数据路径清单（相对项目根，与 .gitignore 语义对齐；archive 后端解压时显式跳过，git 后端靠 gitignore 保留）
USER_DATA_PATHS = [
    'data',
    'plugins/configs',
    'plugins/data',
    'plugins/temp',
    'logs',
    '.plugin_cache',
    'workspace',
    'temp',
    'backups',
]
# 更新下载包存放目录（在 USER_DATA_PATHS 覆盖的 temp/ 下）
DOWNLOAD_DIR = os.path.join('temp', 'update_downloads')
# 框架文件备份目录（在 USER_DATA_PATHS 覆盖的 backups/ 下）
BACKUP_DIR = os.path.join('backups', 'updates')

TIMEOUT = 10  # 下载/网络超时（秒）


# ------------------------------ 工具函数 ------------------------------

def load_global_var():
    """延迟导入 global_var（避免脚本顶层触发其模块副作用）"""
    sys.path.insert(0, BASE_DIR)
    import global_var
    return global_var


def log(msg, level='info'):
    print(f"[update:{level}] {msg}", flush=True)


def run_selfcheck():
    """运行框架启动自检，返回 (ok, fatal, warnings)"""
    sys.path.insert(0, BASE_DIR)
    from core.selfcheck import run_selfcheck
    res = run_selfcheck(verbose=False)
    return res['ok'], res['fatal'], res['warnings']


def is_git_repo(path=None):
    path = path or BASE_DIR
    return os.path.isdir(os.path.join(path, '.git')) or os.path.isdir(os.path.join(path, '.git'))


def parse_version(v):
    parts = []
    for seg in str(v or '').strip().lstrip('vV').split('.'):
        try:
            parts.append(int(seg))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def is_newer(latest, current):
    return parse_version(latest) > parse_version(current)


def path_is_user_data(rel: str) -> bool:
    """判断包内相对路径是否属于用户数据路径（应跳过/保留）"""
    rel = rel.replace('\\', '/').lstrip('/')
    if not rel:
        return False
    top = rel.split('/')[0]
    for ud in USER_DATA_PATHS:
        if rel == ud or rel.startswith(ud + '/'):
            return True
    # 根目录/plugins 散落的运行时文件（与 .gitignore 对齐）
    if rel in ('frontend_tools.json', '.version', 'plugins/status.json'):
        return True
    return False


def check_zip_slip(names):
    """zip slip 防护：拒绝绝对路径 / 上级目录穿越成员"""
    for n in names:
        nn = n.replace('\\', '/')
        if nn.startswith('/') or '..' in nn.split('/'):
            return False, n
    return True, ''


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------ 数据源与校验 ------------------------------

def fetch_changelog(feed_url=None):
    """拉取 changelog.json；返回 dict 或抛异常"""
    gv = load_global_var()
    url = feed_url or gv.get_user_config().get('UPDATE_FEED_URL') or ''
    if not url:
        raise RuntimeError('未配置 UPDATE_FEED_URL（可用 --feed-url 指定）')
    import urllib.request
    req = urllib.request.Request(url, headers={'User-Agent': 'FlaskToolkit/update-tool'})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read().decode('utf-8')
    d = json.loads(raw)
    if not isinstance(d, dict) or 'latest_version' not in d:
        raise RuntimeError('数据源格式错误：缺少 latest_version')
    return d


def verify_changelog_signature(d, gv):
    """配置了 UPDATE_PUBLIC_KEY_PEM 时强制验签 changelog；返回 (ok, msg)"""
    pem = gv.get_user_config().get('UPDATE_PUBLIC_KEY_PEM') or ''
    if not pem:
        return True, '未配置公钥（跳过签名验证）'
    if not os.path.exists(pem):
        return False, f'公钥文件不存在: {pem}'
    fields = ('latest_version', 'published_at', 'download_url', 'sha256', 'changes')
    manifest = {k: d.get(k) for k in fields if k in d}
    try:
        sys.path.insert(0, BASE_DIR)
        from core.package_sign import verify_signature
        return verify_signature(manifest, pem)
    except Exception as e:
        return False, f'签名验证异常: {e}'


def verify_update_archive(zip_path, changelog, gv):
    """更新包完整性校验链：sha256 必选 + 可选签名（zip 内 manifest 由 release.py 生成）+
    zip slip 防护 + manifest.version 与 changelog 一致。返回 (ok, message)。"""
    # 1) sha256（changelog 内）
    expected_sha = (changelog.get('sha256') or '').strip().lower()
    if expected_sha:
        actual = sha256_file(zip_path)
        if actual != expected_sha:
            return False, f'sha256 不匹配（期望 {expected_sha}，实际 {actual}）'
    else:
        return False, 'changelog 缺少 sha256（发布方须用 tools/release.py --write-changelog 生成）'

    # 2) zip 结构与 zip slip
    try:
        zf = zipfile.ZipFile(zip_path, 'r')
    except zipfile.BadZipFile:
        return False, '无效的 zip 文件'
    with zf:
        names = [n.replace('\\', '/') for n in zf.namelist()]
        ok, bad = check_zip_slip(names)
        if not ok:
            return False, f'zip slip 风险成员: {bad}'
        # 3) manifest.version 一致性
        if 'manifest.json' in names:
            try:
                m = json.loads(zf.read('manifest.json').decode('utf-8'))
            except Exception:
                return False, 'manifest.json 解析失败'
            if m.get('version') != changelog.get('latest_version'):
                return False, f'包内版本 {m.get("version")} 与 changelog 版本 {changelog.get("latest_version")} 不一致'
        # 4) 签名（changelog signature → 对 changelog 验签；zip 内文件哈希由 release.py 保证）
        return True, '更新包校验通过'


# ------------------------------ 备份 / 回滚 ------------------------------

def backup_framework(tag=''):
    """备份框架文件（除用户数据路径）到 backups/updates/update_backup_<ts>_<tag>.zip"""
    gv = load_global_var()
    backups_dir = os.path.join(BASE_DIR, BACKUP_DIR)
    os.makedirs(backups_dir, exist_ok=True)
    ts = time.strftime('%Y%m%d_%H%M%S')
    name = f'update_backup_{ts}' + (f'_{tag}' if tag else '') + '.zip'
    out = os.path.join(backups_dir, name)
    count = 0
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(BASE_DIR):
            rel_root = os.path.relpath(root, BASE_DIR).replace('\\', '/')
            if rel_root == '.':
                rel_root = ''
            # 剪枝：跳过用户数据路径与下载目录、.git
            dirs[:] = [d for d in dirs if not path_is_user_data((rel_root + '/' + d).lstrip('/'))
                       and d != '.git' and d != '__pycache__']
            for fn in files:
                rel = (rel_root + '/' + fn).lstrip('/')
                if path_is_user_data(rel):
                    continue
                zf.write(os.path.join(root, fn), arcname=rel)
                count += 1
    log(f'框架文件已备份: {out}（{count} 个文件）')
    return out


def list_update_backups():
    backups_dir = os.path.join(BASE_DIR, BACKUP_DIR)
    if not os.path.isdir(backups_dir):
        return []
    return sorted([f for f in os.listdir(backups_dir) if f.endswith('.zip')], reverse=True)


def rollback_archive(backup_file=None):
    """从框架备份 zip 恢复（用户数据路径不动）"""
    if not backup_file:
        lst = list_update_backups()
        if not lst:
            log('没有可用备份', 'error')
            return False
        backup_file = os.path.join(BASE_DIR, BACKUP_DIR, lst[0])
        log(f'使用最近备份: {lst[0]}')
    if not os.path.exists(backup_file):
        log(f'备份不存在: {backup_file}', 'error')
        return False
    restored = 0
    with zipfile.ZipFile(backup_file, 'r') as zf:
        for n in zf.namelist():
            nn = n.replace('\\', '/')
            if path_is_user_data(nn) or not nn:
                continue
            dest = os.path.join(BASE_DIR, nn)
            if nn.endswith('/'):
                os.makedirs(dest, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with zf.open(n) as src, open(dest, 'wb') as dst:
                shutil.copyfileobj(src, dst)
            restored += 1
    log(f'已从备份恢复 {restored} 个文件')
    return True


# ------------------------------ archive 后端（非 Git） ------------------------------

def apply_archive(changelog, download_url, gv, dry_run=False):
    """archive 后端应用更新"""
    # 1) 下载
    import urllib.request
    os.makedirs(os.path.join(BASE_DIR, DOWNLOAD_DIR), exist_ok=True)
    fname = os.path.basename(download_url.split('?')[0]) or 'update.zip'
    zip_path = os.path.join(BASE_DIR, DOWNLOAD_DIR, fname)
    log(f'下载更新包: {download_url}')
    if not dry_run:
        req = urllib.request.Request(download_url, headers={'User-Agent': 'FlaskToolkit/update-tool'})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp, open(zip_path, 'wb') as f:
            shutil.copyfileobj(resp, f)
    else:
        log('（dry-run）跳过下载')
        return

    # 2) 校验
    ok, msg = verify_update_archive(zip_path, changelog, gv)
    if not ok:
        log(f'更新包校验失败: {msg}', 'error')
        return False
    log(f'更新包校验通过: {msg}')

    # 3) 备份框架文件
    backup_file = backup_framework(tag=f'pre_{changelog["latest_version"]}')
    log(f'备份完成: {backup_file}')

    # 4) 解压替换（跳过用户数据路径）
    log('解压替换框架文件（保留用户数据路径）...')
    skipped = []
    replaced = 0
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for n in zf.namelist():
            nn = n.replace('\\', '/')
            if path_is_user_data(nn) or not nn:
                skipped.append(nn)
                continue
            dest = os.path.join(BASE_DIR, nn)
            if nn.endswith('/'):
                os.makedirs(dest, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with zf.open(n) as src, open(dest, 'wb') as dst:
                shutil.copyfileobj(src, dst)
            replaced += 1
    log(f'替换完成: {replaced} 个文件，保留用户数据路径 {len(skipped)} 项')

    # 5) selfcheck 验证
    ok, fatal, warnings = run_selfcheck()
    if not ok:
        log(f'更新后自检失败: {fatal}', 'error')
        log('自动回滚...')
        rollback_archive(backup_file)
        ok2, _, _ = run_selfcheck()
        log(f'回滚后自检: {"通过" if ok2 else "仍失败（请手动检查备份 " + backup_file + "）"}')
        return False
    log('更新后自检通过 ✓')
    log('更新完成，请重启服务生效。如需回滚: python tools/update.py --rollback')
    return True


# ------------------------------ git 后端 ------------------------------

def apply_git(gv, dry_run=False):
    """git 后端应用更新：fetch → stash → reset → pip install → selfcheck（失败回滚）"""
    cmds = [
        ['git', 'fetch', 'origin', 'main'],
        ['git', 'stash', 'push', '-u'],
        ['git', 'reset', '--hard', 'origin/main'],
    ]
    if not dry_run:
        for cmd in cmds:
            log('执行: ' + ' '.join(cmd))
            r = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True)
            if r.returncode != 0:
                log(f'命令失败: {r.stderr or r.stdout}', 'error')
                return False
    else:
        log('（dry-run）' + ' ; '.join(' '.join(c) for c in cmds))
    # pip install
    pip = ['pip', 'install', '-r', 'requirements.txt']
    if not dry_run:
        r = subprocess.run(pip, cwd=BASE_DIR, capture_output=True, text=True)
        if r.returncode != 0:
            log(f'pip install 失败: {r.stderr or r.stdout}', 'error')
    else:
        log('（dry-run）' + ' '.join(pip))
    # selfcheck
    ok, fatal, _ = run_selfcheck()
    if not ok:
        log(f'更新后自检失败: {fatal}，回滚中...', 'error')
        if not dry_run:
            subprocess.run(['git', 'reset', '--hard', 'HEAD@{1}'], cwd=BASE_DIR, capture_output=True)
            subprocess.run(['git', 'stash', 'pop'], cwd=BASE_DIR, capture_output=True)
        return False
    log('git 后端更新完成 ✓（重启服务生效）')
    return True


# ------------------------------ CLI ------------------------------

def cmd_check(args):
    gv = load_global_var()
    from core.update_checker import check_for_update, is_newer
    info = check_for_update(force=args.force, feed_url=args.feed_url)
    current = gv.FRAMEWORK_VERSION
    if info is None or not info.latest_version:
        print(json.dumps({'ok': False, 'message': '检查失败：无法访问更新数据源'}, ensure_ascii=False))
        return 1
    has_update = is_newer(info.latest_version, current)
    out = {
        'ok': True,
        'current_version': current,
        'latest_version': info.latest_version,
        'published_at': info.published_at,
        'download_url': info.download_url,
        'has_update': has_update,
        'changes': info.changes,
    }
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"当前版本: v{current}")
        print(f"最新版本: v{info.latest_version}" + ('（有新版本！）' if has_update else '（已是最新）'))
        for c in info.changes:
            print(f"  - {c}")
        if has_update:
            print(f"下载: {info.download_url}")
            print("更新: python tools/update.py --apply")
    return 0 if has_update else 0


def cmd_backup(args):
    f = backup_framework(tag=args.tag or 'manual')
    print(f'备份完成: {f}')


def cmd_apply(args):
    gv = load_global_var()
    # 更新前自检
    ok, fatal, _ = run_selfcheck()
    if not ok and not args.dry_run:
        log(f'更新前自检失败，中止（先修复框架完整性）: {fatal}', 'error')
        return 1
    backend = args.backend
    if not backend:
        backend = 'git' if is_git_repo() else 'archive'
    log(f'后端: {backend}')
    if backend == 'git':
        return 0 if apply_git(gv, args.dry_run) else 1
    # archive：读 changelog → 下载 → 应用
    try:
        changelog = fetch_changelog(args.feed_url)
    except Exception as e:
        log(f'读取更新数据源失败: {e}', 'error')
        return 1
    ok, msg = verify_changelog_signature(changelog, gv)
    if not ok:
        log(f'changelog 签名验证失败: {msg}', 'error')
        return 1
    current = gv.FRAMEWORK_VERSION
    if not is_newer(changelog['latest_version'], current):
        log(f'当前已是最新（v{current}），无需更新')
        return 0
    url = changelog.get('download_url') or ''
    if not url:
        log('changelog 缺少 download_url', 'error')
        return 1
    return 0 if apply_archive(changelog, url, gv, args.dry_run) else 1


def cmd_rollback(args):
    ok = rollback_archive(args.backup_file)
    if ok:
        o2, fatal, _ = run_selfcheck()
        log(f'回滚后自检: {"通过 ✓" if o2 else "失败: " + str(fatal)}')
    return 0 if ok else 1


def cmd_selfcheck(args):
    ok, fatal, warnings = run_selfcheck()
    for w in warnings:
        print(f"[自检] 警告: {w}")
    if not ok:
        for f in fatal:
            print(f"[自检] 致命: {f}")
        print("[自检] 失败")
        return 1
    print("[自检] 通过 ✓")
    return 0


def main():
    ap = argparse.ArgumentParser(description='FlaskToolkit 版本更新脚本（git / archive 双后端）')
    sub = ap.add_subparsers(dest='cmd', required=True)

    c = sub.add_parser('check', help='检查新版本')
    c.add_argument('--force', action='store_true', help='强制拉取数据源（跳过缓存）')
    c.add_argument('--feed-url', default=None, help='覆盖 UPDATE_FEED_URL')
    c.add_argument('--json', action='store_true', help='JSON 输出')
    c.set_defaults(func=cmd_check)

    b = sub.add_parser('backup', help='备份当前框架文件')
    b.add_argument('--tag', default=None, help='备份标签')
    b.set_defaults(func=cmd_backup)

    a = sub.add_parser('apply', help='应用更新')
    a.add_argument('--backend', choices=['git', 'archive'], default=None, help='更新后端（默认自动探测）')
    a.add_argument('--dry-run', action='store_true', help='演练模式（不实际下载/替换）')
    a.add_argument('--feed-url', default=None, help='覆盖 UPDATE_FEED_URL')
    a.set_defaults(func=cmd_apply)

    r = sub.add_parser('rollback', help='回滚到最近备份')
    r.add_argument('--backup-file', default=None, help='指定备份 zip（默认最近一次）')
    r.set_defaults(func=cmd_rollback)

    s = sub.add_parser('selfcheck', help='运行启动自检')
    s.set_defaults(func=cmd_selfcheck)

    args = ap.parse_args()
    sys.exit(args.func(args) or 0)


if __name__ == '__main__':
    main()
