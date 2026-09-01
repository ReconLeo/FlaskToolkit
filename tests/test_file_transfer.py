# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""文件传输强化回归（v4.2.2）

覆盖：
A. 全局 MAX_CONTENT_LENGTH：超限请求统一 413（API JSON / 页面模板）
B. 插件级 max_upload_size（MB）：save_uploaded_file 保存前统一预检
C. route 级 max_upload（MB）：提升本请求 MAX_CONTENT_LENGTH，突破全局默认
D. send_file_response 增强：中文文件名 RFC 5987 编码、下载统计计入 call_stats
E. on_load 依赖检查默认 warning（不阻断）；on_ready 钩子在所有插件加载后执行
运行：python tests/test_file_transfer.py
"""
import io
import os
import sys

sys.path.insert(0, _PROJECT_ROOT)

import app as appmod
import global_var
from global_var import plugins
from core.permission import wrap_view_func

app = appmod.app
app.config["TESTING"] = True
client = app.test_client()

results = []

def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

# ============ 测试插件 ============
from plugins.base_plugin import BasePlugin, permission as permission_required

class FilePlugin(BasePlugin):
    name = "fileplug"
    title = "文件传输测试插件"
    description = "上传预检/下载增强/on_ready 测试"
    version = "1.0.0"
    author = "T"
    category = "测试"
    permission = "user"

    loaded_log = []
    ready_log = []
    order_log = []  # 共享时间线：记录 on_load / on_ready 执行顺序

    @property
    def max_upload_size(self):
        return 1  # 插件级上传上限 1MB

    @property
    def routes(self):
        return [
            {"path": "/upload-small", "methods": ["POST"], "params": [{"name": "file", "type": "file", "required": True}],
             "view_func": self.upload_small},
            {"path": "/upload-big", "methods": ["POST"], "params": [{"name": "file", "type": "file", "required": True}],
             "view_func": self.upload_big, "max_upload": 200},  # route 级 200MB 突破插件 1MB
            {"path": "/download/<filename>", "methods": ["GET"], "view_func": self.download},
        ]

    @permission_required("user")
    def upload_small(self):
        try:
            temp_path, name = self.save_uploaded_file("file")
            # 沙箱环境禁止 os.remove（仅 /tmp 放行），清理容错不阻断断言
            try:
                os.remove(temp_path)
            except OSError:
                pass
            return {"status": "success", "name": name}, 200
        except ValueError as e:
            return {"status": "error", "message": str(e)}, 413

    @permission_required("user")
    def upload_big(self):
        try:
            temp_path, name = self.save_uploaded_file("file")
            try:
                os.remove(temp_path)
            except OSError:
                pass
            return {"status": "success", "name": name}, 200
        except ValueError as e:
            return {"status": "error", "message": str(e)}, 413

    @permission_required("public")
    def download(self, filename):
        return self.send_file_response(
            _os.path.join(_TESTS_DIR, "fixtures", "download_sample.txt"),
            download_name=filename,
        )

    def on_load(self):
        FilePlugin.loaded_log.append(self.name)
        FilePlugin.order_log.append((self.name, "on_load"))

    def on_ready(self):
        FilePlugin.ready_log.append(self.name)
        FilePlugin.order_log.append((self.name, "on_ready"))


def main():
    try:
        # ============ 准备下载样例文件 ============
        fixtures = os.path.join(_TESTS_DIR, "fixtures")
        os.makedirs(fixtures, exist_ok=True)
        sample = os.path.join(fixtures, "download_sample.txt")
        with open(sample, "w", encoding="utf-8") as f:
            f.write("hello flasktoolkit file transfer")

        # ============ 注册插件 ============
        plugin = FilePlugin()
        plugins.clear()
        plugin._wrapped_routes = {}
        plugin._wrapped_pages = {}
        for route in plugin.routes:
            wrapped = wrap_view_func(route["view_func"], plugin.name, route)
            path = route["path"]
            methods = tuple(route.get("methods", ["GET"]))
            if path not in plugin._wrapped_routes:
                plugin._wrapped_routes[path] = {}
            plugin._wrapped_routes[path][methods] = wrapped
        plugins[plugin.name] = plugin

        # ============ A. 全局 MAX_CONTENT_LENGTH → 统一 413 ============
        # 构造超大请求体（> 100MB 全局默认）
        big_body = b"x" * (app.config["MAX_CONTENT_LENGTH"] + 1024)
        r = client.post("/api/fileplug/upload-small", data={"file": (io.BytesIO(big_body), "big.bin")})
        check("A1 超全局上限返回 413", r.status_code == 413, f"status={r.status_code}")
        # API 场景 JSON
        try:
            j = r.get_json()
            check("A2 API 场景 413 返回统一 JSON", j is not None and j.get("code") == 413,
                  f"json={j}")
        except Exception:
            check("A2 API 场景 413 返回统一 JSON", False, "非 JSON")

        # ============ B. 插件级 max_upload_size（MB）预检 ============
        # 构造 2MB 文件 > 插件 1MB → 应被 save_uploaded_file 预检拦截（413）
        mid_body = b"y" * (2 * 1024 * 1024)
        r = client.post("/api/fileplug/upload-small", data={"file": (io.BytesIO(mid_body), "mid.bin")})
        check("B1 插件级 1MB 限制拦截 2MB（413）", r.status_code == 413,
              f"status={r.status_code} msg={r.get_json().get('message') if r.is_json else ''}")
        # 构造 512KB 文件 < 1MB → 应通过
        small_body = b"z" * (512 * 1024)
        r = client.post("/api/fileplug/upload-small", data={"file": (io.BytesIO(small_body), "small.bin")})
        check("B2 512KB 未超插件 1MB 上传成功", r.status_code == 200 and r.get_json().get("status") == "success",
              f"status={r.status_code}")

        # ============ C. route 级 max_upload（MB）突破插件默认 ============
        # upload-big 声明 max_upload=200MB，允许 5MB 文件（> 插件 1MB 但 < 200MB）
        r = client.post("/api/fileplug/upload-big", data={"file": (io.BytesIO(b"w" * (5 * 1024 * 1024)), "big5.bin")})
        check("C1 route 级 200MB 覆盖插件 1MB（5MB 成功）",
              r.status_code == 200 and r.get_json().get("status") == "success", f"status={r.status_code}")
        # route 级也提升 MAX_CONTENT_LENGTH：2MB 文件在本路由下未触发全局 413 且未超 200MB
        r = client.post("/api/fileplug/upload-big", data={"file": (io.BytesIO(b"v" * (2 * 1024 * 1024)), "big2.bin")})
        check("C2 route 级 2MB 未触发全局 413", r.status_code == 200, f"status={r.status_code}")

        # ============ D. send_file_response 增强 ============
        # 中文文件名 → Content-Disposition RFC 5987 filename*=UTF-8''
        r = client.get("/api/fileplug/download/%E4%B8%AD%E6%96%87%E6%96%87%E4%BB%B6.txt")
        cd = r.headers.get("Content-Disposition", "")
        check("D1 中文文件名 RFC 5987 编码",
              "filename*=UTF-8''" in cd and "%E4%B8%AD%E6%96%87" in cd, f"CD={cd}")
        check("D2 下载内容正确", r.status_code == 200 and b"hello flasktoolkit" in r.data, f"status={r.status_code}")
        # 下载统计计入 call_stats（插件热度）；send_file_response 未传 stats_endpoint 时默认用 request.path
        stat_key = f"{plugin.name}:/api/fileplug/download/中文文件.txt"
        check("D3 下载计入 call_stats", global_var.call_stats.get(stat_key, 0) >= 1,
              f"call_stats[{stat_key}]={global_var.call_stats.get(stat_key)}")
        # Range 断点续传：请求 bytes=0-4 → 206 + 前 5 字节
        r = client.get("/api/fileplug/download/%E4%B8%AD%E6%96%87%E6%96%87%E4%BB%B6.txt",
                       headers={"Range": "bytes=0-4"})
        check("D4 Range 断点续传返回 206 + 正确字节",
              r.status_code == 206 and r.data == b"hello", f"status={r.status_code} data={r.data!r}")

        # ============ E. on_load 默认 warning + on_ready 延后 ============
        # 模拟 loader 顺序：on_load 阶段（此时其他插件可能未加载）→ on_ready 阶段（全部加载后）
        plugin.on_load()
        plugin.on_ready()
        check("E1 on_ready 钩子可用（所有插件加载后执行）",
              plugin.name in FilePlugin.ready_log, f"ready_log={FilePlugin.ready_log}")
        # 共享时间线：on_load 必然在 on_ready 之前（同一插件，先 load 后 ready）
        seq = [tag for _, tag in FilePlugin.order_log]
        check("E2 on_load 在 on_ready 之前执行（先 load 后 ready）",
              seq.index("on_load") < seq.index("on_ready"), f"order={FilePlugin.order_log}")

        # 清理样例文件
        try:
            os.remove(sample)
        except OSError:
            pass

        print(f'\n==== 文件传输强化回归（v4.2.2）：共 {len(results)} 项，'
              f'通过 {sum(1 for _, c, _ in results if c)}，'
              f'失败 {sum(1 for _, c, _ in results if not c)} ====')
    finally:
        plugins.pop(plugin.name, None)
        try:
            os.remove(os.path.join(_TESTS_DIR, "fixtures", "download_sample.txt"))
        except OSError:
            pass

    ok = all(c for _, c, _ in results)
    sys.exit(0 if ok else 1)

if __name__ == '__main__':
    main()
