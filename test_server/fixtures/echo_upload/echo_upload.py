# -*- coding: utf-8 -*-
"""echo_upload — 测试专用回显上传插件（阶段 3B 大文件压测载体）。

路由：
  POST /api/echo-upload         multipart 单 file 字段 → 落盘 plugins/data/echo_upload/
                                返回 {size, sha256, saved}；可带 form 字段 keep=0 不落盘（纯传输测）。
  GET  /api/echo-upload/<name>  回传文件（下载校验哈希一致性）。
"""
import hashlib
import os

from flask import jsonify, request, send_from_directory

from plugins.base_plugin import BasePlugin


class EchoUploadPlugin(BasePlugin):
    name = 'echo_upload'
    title = '测试：回显上传（大文件压测载体）'

    def routes(self):
        return [
            {
                'path': '/echo-upload',
                'name': '回显上传',
                'methods': ['POST'],
                'params': [
                    {'name': 'file', 'type': 'file', 'required': True, 'description': '任意文件'},
                    {'name': 'keep', 'type': 'string', 'required': False,
                     'description': 'keep=0 仅流式读取返回哈希，不落盘'}
                ],
                'view_func': self.upload_api,
                'permission': 'user',
            },
            {
                'path': '/echo-upload/<name>',
                'name': '回传文件',
                'methods': ['GET'],
                'view_func': self.download_api,
                'permission': 'user',
            },
        ]

    def _data_dir(self):
        d = os.path.join(self.data_dir, 'files')
        os.makedirs(d, exist_ok=True)
        return d

    def upload_api(self):
        f = request.files.get('file')
        if f is None:
            return jsonify({'code': 400, 'message': '缺少 file 字段'}), 400
        keep = request.form.get('keep', '1') != '0'
        h = hashlib.sha256()
        size = 0
        saved = None
        if keep:
            dst = os.path.join(self._data_dir(), os.path.basename(f.filename) or 'upload.bin')
            with open(dst, 'wb') as out:
                while True:
                    blk = f.stream.read(1024 * 1024)
                    if not blk:
                        break
                    h.update(blk)
                    size += len(blk)
                    out.write(blk)
            saved = dst
        else:
            while True:
                blk = f.stream.read(1024 * 1024)
                if not blk:
                    break
                h.update(blk)
                size += len(blk)
        return jsonify({'code': 0, 'size': size, 'sha256': h.hexdigest(),
                        'saved': saved is not None})

    def download_api(self, name):
        return send_from_directory(self._data_dir(), name, as_attachment=True)
