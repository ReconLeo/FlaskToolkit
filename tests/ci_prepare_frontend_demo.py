# -*- coding: utf-8 -*-
# CI 辅助：预生成 verify_frontend_chain.py 依赖的 demo_tool 工具包（v1.0.0 / v1.0.1）。
# verify_frontend_chain.py 从 temp/demo_tool_v1.0.0.zip 与 temp/demo_tool_v1.0.1.zip 上传/更新/卸载，
# 其断言对 zip 内容有要求（见下），生成内容须与其对齐：
#   - v1.0.0：config.json(version=1.0.0) + demo_tool.html 含 "1.0.0" + static/css/style.css + static/js/app.js + static/js/old.js
#   - v1.0.1：config.json(version=1.0.1) + demo_tool.html 含 "1.0.1"/"v2-badge" 且不含 ">1.0.0<" + static/css/style.css 含 ".v2-badge" + static/js/app.js（无 old.js，更新后应 404）
import io
import json
import os
import sys
import zipfile

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TEMP = os.path.join(_PROJECT_ROOT, 'temp')


def build_zip(name, version, html, static_files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('config.json', json.dumps({
            "name": name, "version": version, "category": "测试",
            "title": name, "author": "T", "description": "链测",
        }, ensure_ascii=False).encode('utf-8'))
        zf.writestr(f'{name}.html', html)
        for path, content in static_files.items():
            zf.writestr(path, content)
    return buf.getvalue()


def main():
    os.makedirs(_TEMP, exist_ok=True)
    v1 = build_zip('demo_tool', '1.0.0',
                   '<html><body>demo 1.0.0</body></html>',
                   {'static/css/style.css': 'body{}',
                    'static/js/app.js': 'var x = 1;',
                    'static/js/old.js': 'var old = 1;'})
    v2 = build_zip('demo_tool', '1.0.1',
                   '<html><body>demo 1.0.1 <span>v2-badge</span></body></html>',
                   {'static/css/style.css': '.v2-badge{color:red}',
                    'static/js/app.js': 'var x = 2;'})
    p1 = os.path.join(_TEMP, 'demo_tool_v1.0.0.zip')
    p2 = os.path.join(_TEMP, 'demo_tool_v1.0.1.zip')
    with open(p1, 'wb') as f:
        f.write(v1)
    with open(p2, 'wb') as f:
        f.write(v2)
    print('已生成:', p1, os.path.getsize(p1), 'bytes')
    print('已生成:', p2, os.path.getsize(p2), 'bytes')


if __name__ == '__main__':
    sys.exit(main() or 0)
