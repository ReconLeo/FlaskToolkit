# -*- coding: utf-8 -*-
"""
FlaskToolkit 官方示例一键安装 / 卸载 / 打包脚本
==================================================
用法（在项目根目录执行）：

    # 1. 打包所有示例为 zip 到 examples/dist/（不依赖服务，仅验证包结构）
    python examples/install_all.py --pack-only

    # 2. 一键安装到运行中的服务（需先启动 python app.py，并配置管理员账号）
    python examples/install_all.py
    python examples/install_all.py --base-url http://127.0.0.1:5000 \
        --username admin --password admin123

    # 3. 一键卸载所有示例
    python examples/install_all.py --uninstall

说明：
- 通过框架正式 API 安装（登录 → CSRF → 上传 zip），走完整安装链路（溯源/审计）。
- 安装依赖 requests（见 requirements-dev.txt）。
- 后端插件 dependent_demo 依赖 auth 插件，auth 未安装时该插件会被拒绝安装。
"""
import argparse
import io
import json
import os
import sys
import zipfile

try:
    import requests
except ImportError:
    print("缺少 requests，请先安装：pip install -r requirements.txt -r requirements-dev.txt")
    sys.exit(1)

EXAMPLES_DIR = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(EXAMPLES_DIR, 'manifest.json')
DIST_DIR = os.path.join(EXAMPLES_DIR, 'dist')

# 上传接口
UPLOAD_API = {
    'backend': '/api/admin/plugins/upload',
    'frontend': '/api/admin/frontend/upload',
}
UNINSTALL_API = {
    'backend': lambda name: f'/api/admin/plugins/{name}/uninstall',
    'frontend': lambda name: f'/api/admin/frontend/{name}/uninstall',
}


def load_manifest():
    with open(MANIFEST, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_zip(src_dir: str, out_zip: str):
    """把示例源目录打包为 zip（目录结构即插件包结构，正斜杠分隔）"""
    if not os.path.isdir(src_dir):
        raise FileNotFoundError(f"示例目录不存在: {src_dir}")
    os.makedirs(os.path.dirname(out_zip), exist_ok=True)
    with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(src_dir):
            for fname in files:
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, src_dir).replace('\\', '/')
                zf.write(full, rel)
    return out_zip


def pack_all():
    """把所有示例打包到 examples/dist/，返回 {名称: zip路径}"""
    manifest = load_manifest()
    results = {}
    for group in ('plugins', 'frontend_tools'):
        for item in manifest[group]:
            name = item['name']
            src = os.path.join(EXAMPLES_DIR, item['path'])
            out = os.path.join(DIST_DIR, f"{name}.zip")
            build_zip(src, out)
            results[name] = out
            print(f"[打包] {name} -> examples/dist/{name}.zip")
    return results


class ApiClient:
    """登录态 + CSRF 的 HTTP 客户端"""

    def __init__(self, base_url: str, username: str, password: str):
        self.base = base_url.rstrip('/')
        self.session = requests.Session()
        self.csrf = None
        self._login(username, password)

    def _login(self, username: str, password: str):
        resp = self.session.post(
            f"{self.base}/api/auth/login",
            json={"username": username, "password": password},
        )
        data = resp.json()
        if resp.status_code != 200 or data.get("code") != 200:
            raise RuntimeError(
                f"登录失败: {data.get('message', resp.text)}"
            )
        # csrf_token 为普通 Cookie（非 HttpOnly），前端可读
        self.csrf = self.session.cookies.get('csrf_token')
        if not self.csrf:
            raise RuntimeError("登录成功但未获取到 csrf_token Cookie")
        print(f"[登录] 成功，用户 {username}")

    def _headers(self):
        headers = {}
        if self.csrf:
            headers['X-CSRF-Token'] = self.csrf
        return headers

    def install(self, name: str, zip_path: str, type_: str) -> bool:
        api = UPLOAD_API[type_]
        with open(zip_path, 'rb') as f:
            resp = self.session.post(
                f"{self.base}{api}",
                files={'file': (f"{name}.zip", f, 'application/zip')},
                headers=self._headers(),
            )
        try:
            data = resp.json()
            msg = data.get('message', resp.text)
        except Exception:
            msg = resp.text
        if resp.status_code == 200 and (data.get('code') == 200 if isinstance(data, dict) else True):
            print(f"[安装] {name}（{type_}）成功: {msg}")
            return True
        # 幂等：已存在同名则跳过（重复运行不报错）
        if resp.status_code == 400 and ('已存在' in msg or '同名' in msg):
            print(f"[跳过] {name}（{type_}）已存在: {msg}")
            return True
        print(f"[安装] {name}（{type_}）失败 [HTTP {resp.status_code}]: {msg}")
        return False

    def uninstall(self, name: str, type_: str) -> bool:
        api = UNINSTALL_API[type_](name)
        resp = self.session.post(f"{self.base}{api}", headers=self._headers())
        try:
            data = resp.json()
            msg = data.get('message', resp.text)
        except Exception:
            msg = resp.text
        ok = resp.status_code == 200 and (data.get('code') == 200 if isinstance(data, dict) else True)
        print(f"[卸载] {name}（{type_}）{'成功' if ok else '失败'}: {msg}")
        return ok


def install_all(client: ApiClient, zips: dict):
    manifest = load_manifest()
    ok, fail = 0, 0
    for group, type_ in (('plugins', 'backend'), ('frontend_tools', 'frontend')):
        for item in manifest[group]:
            name = item['name']
            if client.install(name, zips[name], type_):
                ok += 1
            else:
                fail += 1
    print(f"\n==== 安装完成：成功 {ok}，失败 {fail} ====")
    return fail == 0


def uninstall_all(client: ApiClient):
    manifest = load_manifest()
    ok, fail = 0, 0
    for group, type_ in (('plugins', 'backend'), ('frontend_tools', 'frontend')):
        for item in manifest[group]:
            name = item['name']
            if client.uninstall(name, type_):
                ok += 1
            else:
                fail += 1
    print(f"\n==== 卸载完成：成功 {ok}，失败 {fail} ====")
    return fail == 0


def main():
    parser = argparse.ArgumentParser(description="FlaskToolkit 示例一键安装/卸载/打包")
    parser.add_argument('--pack-only', action='store_true', help='仅打包到 examples/dist/，不安装')
    parser.add_argument('--uninstall', action='store_true', help='卸载所有示例（需服务运行）')
    parser.add_argument('--base-url', default='http://127.0.0.1:5000', help='服务地址')
    parser.add_argument('--username', default='admin', help='管理员用户名')
    parser.add_argument('--password', default='admin123', help='管理员密码')
    args = parser.parse_args()

    zips = pack_all()
    if args.pack_only:
        print("已打包到 examples/dist/，可手动在管理后台上传或使用 --uninstall/默认安装。")
        return

    try:
        client = ApiClient(args.base_url, args.username, args.password)
    except RuntimeError as e:
        print(f"连接失败：{e}")
        print("请先启动服务：python app.py（并确认管理员账号）。")
        sys.exit(1)

    if args.uninstall:
        sys.exit(0 if uninstall_all(client) else 1)
    sys.exit(0 if install_all(client, zips) else 1)


if __name__ == '__main__':
    main()
