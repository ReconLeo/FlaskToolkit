# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""zip slip（路径穿越）专项单元测试：core/plugin_pack.py

覆盖场景：
1. parse_plugin_pack 描述文件校验（缺失/非法 JSON/缺 name/主 .py 文件名不匹配）
2. extract_plugin_pack 解压安全（拒绝 .. 穿越 / 绝对路径 / 盘符路径 / 反斜杠变体）
3. 正常插件包解压落位（正向控制组）

运行：python test_zip_slip.py（不依赖 Flask 服务，纯单元测试）
"""
import json
import os
import shutil
import sys
import tempfile
import zipfile

sys.path.insert(0, _PROJECT_ROOT)

import global_var
from core.plugin_pack import (
    parse_plugin_pack,
    extract_plugin_pack,
    PLUGIN_PACK_DESC_FILE,
)

results = []


def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")


class TmpBase:
    """临时项目根：mock global_var.BASE_DIR，测试后清理（try/except 容忍）"""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix='zipslip_')
        self._old = None

    def __enter__(self):
        self._old = global_var.BASE_DIR
        global_var.BASE_DIR = self.root
        return self.root

    def __exit__(self, *exc):
        global_var.BASE_DIR = self._old
        try:
            shutil.rmtree(self.root, ignore_errors=True)
        except Exception:
            pass  # 清理失败不阻断测试（如受限环境）


def make_zip(path, entries):
    """entries: [(member_name, content_bytes), ...]"""
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries:
            zf.writestr(name, content)


def test_parse_plugin_pack():
    with TmpBase() as root:
        zip_path = os.path.join(root, 'p.zip')

        # 1. 缺 plugin.json
        make_zip(zip_path, [('user_manage.py', b'x')])
        try:
            parse_plugin_pack(zip_path)
            check('缺 plugin.json 拒绝', False, '未抛异常')
        except ValueError as e:
            check('缺 plugin.json 拒绝', '缺少描述文件' in str(e), str(e)[:40])

        # 2. plugin.json 非法 JSON
        make_zip(zip_path, [('plugin.json', b'{bad json'), ('user_manage.py', b'x')])
        try:
            parse_plugin_pack(zip_path)
            check('非法 JSON 拒绝', False, '未抛异常')
        except ValueError as e:
            check('非法 JSON 拒绝', 'JSON' in str(e), str(e)[:40])

        # 3. 缺 name 字段
        make_zip(zip_path, [
            ('plugin.json', json.dumps({'version': '1.0.0'}).encode('utf-8')),
            ('user_manage.py', b'x'),
        ])
        try:
            parse_plugin_pack(zip_path)
            check('缺 name 拒绝', False, '未抛异常')
        except ValueError as e:
            check('缺 name 拒绝', 'name' in str(e), str(e)[:40])

        # 4. name 与主 .py 文件名不匹配
        make_zip(zip_path, [
            ('plugin.json', json.dumps({'name': 'user_manage'}).encode('utf-8')),
            ('other.py', b'x'),
        ])
        try:
            parse_plugin_pack(zip_path)
            check('name 与主 .py 不匹配拒绝', False, '未抛异常')
        except ValueError as e:
            check('name 与主 .py 不匹配拒绝', '缺少主插件文件' in str(e), str(e)[:40])

        # 5. 正常包解析
        make_zip(zip_path, [
            ('plugin.json', json.dumps({'name': 'user_manage', 'version': '1.0.1'}).encode('utf-8')),
            ('user_manage.py', b'x'),
        ])
        desc = parse_plugin_pack(zip_path)
        check('正常包解析', desc.get('name') == 'user_manage', f"desc={desc}")


def _expect_reject(entries, label):
    """断言 extract_plugin_pack 对该恶意包抛 ValueError"""
    with TmpBase() as root:
        zip_path = os.path.join(root, 'evil.zip')
        make_zip(zip_path, entries)
        try:
            extract_plugin_pack(zip_path, 'plugin_x')
            check(label, False, '未抛异常！存在路径穿越风险')
        except ValueError as e:
            check(label, True, str(e)[:50])


def test_extract_rejects_zip_slip():
    cases = [
        ('相对穿越 ../evil.py', [('../evil.py', b'x')]),
        ('反斜杠穿越 ..\\\\evil.py', [(r'..\evil.py', b'x')]),
        ('深层穿越 templates/../../evil.txt', [('templates/../../evil.txt', b'x')]),
        ('反斜杠深层穿越 templates\\\\..\\\\evil.txt', [(r'templates\..\evil.txt', b'x')]),
        ('绝对路径 /etc/evil.txt', [('/etc/evil.txt', b'x')]),
        ('绝对路径 /evil.py', [('/evil.py', b'x')]),
        ('盘符路径 C:/evil.txt', [('C:/evil.txt', b'x')]),
        ('盘符路径 c:\\\\evil.txt', [(r'c:\evil.txt', b'x')]),
        ('盘符路径 C:\\\\evil.py', [(r'C:\evil.py', b'x')]),
        ('混合：正常 + 穿越条目', [
            ('plugin.json', b'{}'),
            ('good.py', b'x'),
            ('static/../evil.txt', b'x'),
        ]),
    ]
    for label, entries in cases:
        _expect_reject(entries, label)


def test_extract_normal_pack():
    """正向控制组：正常插件包解压到正确位置"""
    with TmpBase() as root:
        zip_path = os.path.join(root, 'ok.zip')
        make_zip(zip_path, [
            ('plugin.json', json.dumps({'name': 'demo', 'version': '1.0.0'}).encode('utf-8')),
            ('demo.py', b'class Demo: pass'),
            ('templates/demo.html', b'<html>demo</html>'),
            ('templates/sub/x.html', b'<html>x</html>'),
            ('static/css/style.css', b'body{}'),
            ('static/js/app.js', b'console.log(1)'),
        ])
        result = extract_plugin_pack(zip_path, 'demo')

        ok = True
        ok &= os.path.isfile(os.path.join(root, 'plugins', 'demo.py'))
        ok &= os.path.isfile(os.path.join(root, 'plugins', 'demo.json'))
        ok &= os.path.isfile(os.path.join(root, 'templates', 'plugins', 'demo', 'demo.html'))
        ok &= os.path.isfile(os.path.join(root, 'templates', 'plugins', 'demo', 'sub', 'x.html'))
        ok &= os.path.isfile(os.path.join(root, 'templates', 'plugins', 'static', 'demo', 'css', 'style.css'))
        ok &= os.path.isfile(os.path.join(root, 'templates', 'plugins', 'static', 'demo', 'js', 'app.js'))
        check('正常包解压落位', ok, f"result={result}")

        # 越界检查：临时根之外不应有任何写入
        parent = os.path.dirname(root)
        escaped = [
            os.path.join(parent, 'evil.txt'),
            os.path.join(parent, 'demo.py'),
        ]
        check('无越界文件写入', not any(os.path.exists(p) for p in escaped), f"parent={parent}")

        # 返回结构字段
        check('result.main 指向主文件',
              result['main'] == os.path.join(root, 'plugins', 'demo.py'),
              f"main={result['main']}")
        check('result.meta 指向描述文件',
              result['meta'] == os.path.join(root, 'plugins', 'demo.json'),
              f"meta={result['meta']}")


if __name__ == '__main__':
    test_parse_plugin_pack()
    test_extract_rejects_zip_slip()
    test_extract_normal_pack()

    passed = sum(1 for _, c, _ in results if c)
    print(f"\n==== zip slip 专项 共 {len(results)} 项，通过 {passed}，失败 {len(results) - passed} ====")
    sys.exit(0 if passed == len(results) else 1)
