# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""BasePlugin.save_uploads 同步持久化上传助手专项（v4.18，§6.1/§6.2）

覆盖（对应设计文档 tests/test_plugin_uploads.py T1–T11）：
T1 单文件保存 / T2 多文件 getlist / T3 单文件大小超限（不落盘）/
T4a 存储配额超限 / T4b 未配置配额放行 / T5a 净化防路径穿越 / T5b 中文名保留 /
T5c sanitize=False 原始名 / T6a 同请求重名去重 / T6b 跨请求重名加序号 / T6c dedup=False 覆盖 /
T7 allowed_upload_types 拒绝 / T8a file_key 缺失 / T8b 空 getlist / T8c 个别空 filename 跳过 /
T9 部分成功 / T10a dest 自动创建 / T10b dest+upload_dir 皆空 ValueError / T11 enforce 交叉校验未声明目录

隔离目录模式：mock global_var.BASE_DIR 到临时目录 + sys.path 指向临时 plugins 包，
不污染真实项目（上传落盘到临时 uploads/）。

运行：python tests/test_plugin_uploads.py
"""
import io
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, _PROJECT_ROOT)

import app as appmod
import global_var
from global_var import plugins
from core.permission import wrap_view_func
from core import capabilities as caps_mod
from core import quota as quota_mod

# ---------- 隔离目录：mock BASE_DIR + sys.path ----------
_isolated = tempfile.mkdtemp(prefix='ftk_uploads_')
os.makedirs(os.path.join(_isolated, 'plugins'))
shutil.copy(os.path.join(_PROJECT_ROOT, 'plugins', '__init__.py'),
            os.path.join(_isolated, 'plugins', '__init__.py'))
shutil.copy(os.path.join(_PROJECT_ROOT, 'plugins', 'base_plugin.py'),
            os.path.join(_isolated, 'plugins', 'base_plugin.py'))
sys.path.insert(0, _isolated)
_SAVED_BASE = global_var.BASE_DIR
global_var.BASE_DIR = _isolated

app = appmod.app
app.config["TESTING"] = True
client = app.test_client()

results = []

def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

from plugins.base_plugin import BasePlugin, permission as permission_required

class UploadPlugin(BasePlugin):
    name = "upld"
    title = "同步上传助手测试插件"
    description = "save_uploads/sanitize_filename 测试"
    version = "1.0.0"
    author = "T"
    category = "测试"
    permission = "user"

    @property
    def allowed_upload_types(self):
        return ['.txt']

    @property
    def upload_dir(self):
        return 'uploads'  # 相对 BASE_DIR（隔离目录）

    def _do_upload(self, **kwargs):
        res = self.save_uploads('files', **kwargs)
        return {'results': res}

    @property
    def routes(self):
        return [
            {"path": "/upload", "methods": ["POST"], "params": [{"name": "files", "type": "file", "required": True}],
             "view_func": lambda: self._do_upload()},
            {"path": "/upload-nodedup", "methods": ["POST"], "params": [{"name": "files", "type": "file", "required": True}],
             "view_func": lambda: self._do_upload(dedup=False)},
            {"path": "/upload-raw", "methods": ["POST"], "params": [{"name": "files", "type": "file", "required": True}],
             "view_func": lambda: self._do_upload(sanitize=False)},
            {"path": "/upload-limit", "methods": ["POST"], "params": [{"name": "files", "type": "file", "required": True}],
             "view_func": lambda: self._do_upload(max_upload_mb=1)},
        ]

def _register_plugin(plugin):
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
    return plugin

plugin = _register_plugin(UploadPlugin())

def _post(path, files):
    """files: list[(bytes, filename)]"""
    data = {'files': [(io.BytesIO(b), fn) for b, fn in files]}
    return client.post(f"/api/upld/{path}", data=data,
                       content_type='multipart/form-data')

def _updir():
    return os.path.join(global_var.BASE_DIR, 'uploads')

def main():
    try:
        # ---------- T1 单文件保存 ----------
        r = _post('upload', [(b'hello world', 'hello.txt')])
        j = r.get_json()['results']
        check("T1 单文件保存",
              len(j) == 1 and j[0]['status'] == 'saved' and j[0]['saved_name'] == 'hello.txt'
              and j[0]['path'] and os.path.exists(j[0]['path'])
              and open(j[0]['path'], 'rb').read() == b'hello world',
              f"j0={j[0] if j else None}")

        # ---------- T2 多文件 getlist ----------
        r = _post('upload', [(b'a', 'a.txt'), (b'b', 'b.txt'), (b'c', 'c.txt')])
        j = r.get_json()['results']
        check("T2 多文件 getlist",
              len(j) == 3 and all(x['status'] == 'saved' for x in j)
              and [x['saved_name'] for x in j] == ['a.txt', 'b.txt', 'c.txt'],
              f"names={[x['saved_name'] for x in j]}")

        # ---------- T3 单文件大小超限（route 级 1MB，不落盘） ----------
        big = b'x' * (2 * 1024 * 1024)
        r = _post('upload-limit', [(big, 'big.txt')])
        j = r.get_json()['results']
        check("T3 大小超限拒绝且不落盘",
              len(j) == 1 and j[0]['status'] == 'rejected' and j[0]['reason'] == 'size_exceeded'
              and j[0]['limit_mb'] == 1.0
              and not os.path.exists(os.path.join(_updir(), 'big.txt')),
              f"j0={j[0] if j else None}")

        # ---------- T4a 存储配额超限 ----------
        caps_mod.register_capabilities('upld', ['storage:limit:1', 'filesystem:write:uploads/**'])
        quota_mod._data_dir_cache.pop('upld', None)
        r = _post('upload', [(b'z' * (2 * 1024 * 1024), 'quota.txt')])
        j = r.get_json()['results']
        check("T4a 配额超限拒绝",
              len(j) == 1 and j[0]['status'] == 'rejected' and j[0]['reason'] == 'quota_exceeded'
              and j[0]['remaining_mb'] is not None and j[0]['remaining_mb'] >= 0,
              f"j0={j[0] if j else None}")
        caps_mod.unregister_capabilities('upld')
        quota_mod._data_dir_cache.pop('upld', None)

        # ---------- T4b 未配置配额（默认 50MB）放行 ----------
        r = _post('upload', [(b'ok', 'ok.txt')])
        j = r.get_json()['results']
        check("T4b 未配置配额放行", len(j) == 1 and j[0]['status'] == 'saved', f"j0={j[0] if j else None}")

        # ---------- T5a 净化防路径穿越 ----------
        r = _post('upload', [(b'p', '../../etc/passwd.txt'), (b'q', 'a/b.txt'), (b'z', '<bad>|*.txt')])
        j = r.get_json()['results']
        names = [x['saved_name'] for x in j]
        check("T5a 净化防路径穿越",
              all(x['status'] == 'saved' for x in j)
              and all('/' not in n and '\\' not in n and not n.startswith('.') and '..' not in n
                      and not any(c in n for c in '<>|*') for n in names),
              f"names={names}")
        # 确认无文件写到 uploads 之外的路径
        check("T5a 无越界落盘",
              os.path.exists(os.path.join(_updir(), 'etcpasswd.txt'))
              and os.path.exists(os.path.join(_updir(), 'ab.txt')),
              f"dirlist={sorted(os.listdir(_updir()))}")

        # ---------- T5b 中文文件名保留 ----------
        r = _post('upload', [(b'cn', '中文文件.txt')])
        j = r.get_json()['results']
        check("T5b 中文文件名保留",
              len(j) == 1 and j[0]['saved_name'] == '中文文件.txt' and os.path.exists(j[0]['path']),
              f"name={j[0]['saved_name'] if j else ''}")

        # ---------- T5c sanitize=False 原始名（前导点不净化） ----------
        r = _post('upload-raw', [(b'raw', '..hidden.txt')])
        j = r.get_json()['results']
        check("T5c sanitize=False 原始名保留前导点", len(j) == 1 and j[0]['saved_name'] == '..hidden.txt',
              f"name={j[0]['saved_name'] if j else ''}")
        # 清理 raw 目录残留避免影响后续
        shutil.rmtree(_updir(), ignore_errors=True)
        os.makedirs(_updir(), exist_ok=True)

        # ---------- T6a 同请求重名去重 ----------
        r = _post('upload', [(b'1', 'dup.txt'), (b'2', 'dup.txt')])
        j = r.get_json()['results']
        check("T6a 同请求重名去重",
              [x['saved_name'] for x in j] == ['dup.txt', 'dup_1.txt'],
              f"names={[x['saved_name'] for x in j]}")

        # ---------- T6b 跨请求重名加序号 ----------
        r = _post('upload', [(b'new', 'dup.txt')])
        j = r.get_json()['results']
        check("T6b 跨请求重名加序号", len(j) == 1 and j[0]['saved_name'] == 'dup_2.txt',
              f"name={j[0]['saved_name'] if j else ''}")

        # ---------- T6c dedup=False 覆盖 ----------
        r = _post('upload-nodedup', [(b'overwrite', 'dup.txt')])
        j = r.get_json()['results']
        check("T6c dedup=False 覆盖同名",
              len(j) == 1 and j[0]['saved_name'] == 'dup.txt'
              and open(j[0]['path'], 'rb').read() == b'overwrite',
              f"name={j[0]['saved_name'] if j else ''}")

        # ---------- T7 allowed_upload_types 拒绝 ----------
        r = _post('upload', [(b'exe', 'bad.exe')])
        j = r.get_json()['results']
        check("T7 类型拒绝", len(j) == 1 and j[0]['status'] == 'rejected' and j[0]['reason'] == 'invalid_type',
              f"j0={j[0] if j else ''}")

        # ---------- T8a file_key 缺失（ValueError） ----------
        with app.test_request_context('/u', method='POST',
                                      data={'other': (io.BytesIO(b'x'), 'x.txt')},
                                      content_type='multipart/form-data'):
            try:
                plugin.save_uploads('files')
                check("T8a file_key 缺失抛 ValueError", False, '未抛异常')
            except ValueError as e:
                check("T8a file_key 缺失抛 ValueError", '缺少上传文件' in str(e), str(e))

        # ---------- T8b 键存在但空 getlist（ValueError） ----------
        # Flask 上传字段存在时至少含一个空条目，此处用 fake request 直接验证 getlist 为空的 guard
        import plugins.base_plugin as bp_mod
        from flask import request as _real_req
        class _EmptyFiles:
            def __contains__(self, key):
                return key == 'files'
            def getlist(self, key):
                return []
        class _FakeReq:
            files = _EmptyFiles()
        bp_mod.request = _FakeReq()
        try:
            plugin.save_uploads('files', dest_dir=_updir())
            check("T8b 空 getlist 抛 ValueError", False, '未抛异常')
        except ValueError as e:
            check("T8b 空 getlist 抛 ValueError", '未选择文件' in str(e), str(e))
        finally:
            bp_mod.request = _real_req

        # ---------- T8c 个别空 filename 跳过，其余正常 ----------
        r = _post('upload', [(b'good', 'good.txt'), (b'', '')])
        j = r.get_json()['results']
        check("T8c 空 filename 跳过", len(j) == 1 and j[0]['saved_name'] == 'good.txt',
              f"len={len(j)} j={j}")

        # ---------- T9 部分成功（一超限一正常） ----------
        r = _post('upload-limit', [(b'x' * (2 * 1024 * 1024), 'big.txt'), (b'small', 'small.txt')])
        j = r.get_json()['results']
        check("T9 部分成功",
              len(j) == 2 and j[0]['status'] == 'rejected' and j[0]['reason'] == 'size_exceeded'
              and j[1]['status'] == 'saved' and os.path.exists(j[1]['path']),
              f"statuses={[x['status'] for x in j]}")

        # ---------- T10a dest 不存在自动创建 ----------
        newdir = os.path.join(_isolated, 'new_sub', 'deep')
        with app.test_request_context('/u', method='POST',
                                      data={'files': (io.BytesIO(b'n'), 'n.txt')},
                                      content_type='multipart/form-data'):
            res = plugin.save_uploads('files', dest_dir=newdir)
            check("T10a dest 不存在自动创建",
                  res[0]['status'] == 'saved' and os.path.isdir(newdir) and os.path.exists(res[0]['path']),
                  f"res={res[0]}")

        # ---------- T10b dest 与 upload_dir 皆空（ValueError） ----------
        class NoDir(UploadPlugin):
            @property
            def upload_dir(self):
                return None
        with app.test_request_context('/u', method='POST',
                                      data={'files': (io.BytesIO(b'x'), 'x.txt')},
                                      content_type='multipart/form-data'):
            try:
                NoDir().save_uploads('files')
                check("T10b dest+upload_dir 皆空抛 ValueError", False, '未抛异常')
            except ValueError as e:
                check("T10b dest+upload_dir 皆空抛 ValueError", '未指定上传目录' in str(e), str(e))

        # ---------- T11 enforce 交叉校验未声明目录 ----------
        # 插件声明不含 uploads 的 filesystem:write → 交叉校验应报 missing（enforce 拒绝依据）
        from core.capabilities import cross_validate
        scan_report = {'scope': {'paths_written': [_updir()], 'paths_read': [], 'network_endpoints': []}}
        cv = cross_validate('upld', scan_report, ['filesystem:write:other/**'], base_dir=global_var.BASE_DIR)
        check("T11 未声明目录交叉校验 missing",
              any('uploads' in m for m in cv.get('missing', [])),
              f"missing={cv.get('missing')}")

        # ---------- 隔离目录未污染真实项目 ----------
        check("真实项目未污染",
              not os.path.exists(os.path.join(_PROJECT_ROOT, 'plugins', 'data', 'upld')))

    finally:
        global_var.BASE_DIR = _SAVED_BASE
        caps_mod.clear_capabilities()
        try:
            shutil.rmtree(_isolated, ignore_errors=True)
        except Exception:
            pass

    passed = sum(1 for _, c, _ in results if c)
    print(f"\n==== 同步上传助手 save_uploads：共 {len(results)} 项，通过 {passed}，失败 {len(results) - passed} ====")
    sys.exit(0 if passed == len(results) else 1)

if __name__ == '__main__':
    main()
