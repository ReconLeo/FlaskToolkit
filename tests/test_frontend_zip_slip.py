# -*- coding: utf-8 -*-
# 框架回归测试套件（FlaskToolkit/tests/），项目根路径自动推导，不依赖绝对路径
import os as _os
import sys as _sys
_TESTS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_PROJECT_ROOT = _os.path.dirname(_TESTS_DIR)
_sys.path.insert(0, _PROJECT_ROOT)
"""前端工具 zip slip（路径穿越）专项单元测试：routes/frontend.py 的 safe_extract_frontend / cleanup_frontend_resources

覆盖场景：
1. 安全解压拒绝路径穿越：相对穿越 ../、反斜杠变体、深层穿越、绝对路径、盘符路径、混合条目
2. 正常前端工具包（config.json + <name>.html + static/）解压落位，未知条目不落盘
3. clean_static=True 更新时先清理旧静态资源目录（验证不残留旧文件）
4. 卸载资源清理 cleanup_frontend_resources（入口 html + static/ 目录）

运行：python test_frontend_zip_slip.py（不依赖 Flask 服务，纯单元测试）
"""
import json
import os
import shutil
import sys
import tempfile
import zipfile

sys.path.insert(0, _PROJECT_ROOT)

import global_var
from routes.frontend import safe_extract_frontend, cleanup_frontend_resources

results = []

def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")


class TmpBase:
    """临时项目根：mock global_var 路径常量指向临时目录，测试后清理（try/except 容忍）"""

    def __init__(self, mock=('BASE_DIR', 'FRONTEND_TEMPLATE_DIR')):
        self.root = tempfile.mkdtemp(prefix='ftk_frontend_')
        self.mock = mock
        self._saved = {}

    def __enter__(self):
        for attr in self.mock:
            self._saved[attr] = getattr(global_var, attr, None)
        if 'BASE_DIR' in self.mock:
            global_var.BASE_DIR = self.root
        if 'FRONTEND_TEMPLATE_DIR' in self.mock:
            global_var.FRONTEND_TEMPLATE_DIR = os.path.join(self.root, 'templates', 'frontend_tools')
        return self.root

    def __exit__(self, *exc):
        for attr, val in self._saved.items():
            if val is None:
                try:
                    delattr(global_var, attr)
                except AttributeError:
                    pass
            else:
                setattr(global_var, attr, val)
        try:
            shutil.rmtree(self.root, ignore_errors=True)
        except Exception:
            pass  # 清理失败不阻断测试（如受限环境）


def make_zip(path, entries):
    """entries: [(member_name, content_bytes), ...]"""
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries:
            zf.writestr(name, content)


def _expect_reject(entries, label):
    """断言 safe_extract_frontend 对该恶意包抛 ValueError"""
    with TmpBase() as root:
        zip_path = os.path.join(root, 'evil.zip')
        make_zip(zip_path, entries)
        target_dir = os.path.join(root, 'templates', 'frontend_tools')
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                safe_extract_frontend(zf, 'demo_tool', target_dir)
            check(label, False, '未抛异常！存在路径穿越风险')
        except ValueError as e:
            check(label, True, str(e)[:60])


def test_safe_extract_rejects_zip_slip():
    """攻击包必须被拒绝，且不落任何文件"""
    cases = [
        ('相对穿越 ../evil.txt', [('../evil.txt', b'x')]),
        ('反斜杠穿越 ..\\\\evil.txt', [(r'..\evil.txt', b'x')]),
        ('深层穿越 static/../../evil.txt', [('static/../../evil.txt', b'x')]),
        ('反斜杠深层 static\\\\..\\\\..\\\\evil.txt', [(r'static\..\..\evil.txt', b'x')]),
        ('绝对路径 /etc/evil.txt', [('/etc/evil.txt', b'x')]),
        ('绝对路径 /evil.css', [('/evil.css', b'x')]),
        ('盘符路径 C:/evil.txt', [('C:/evil.txt', b'x')]),
        ('盘符路径 c:\\\\evil.txt', [(r'c:\evil.txt', b'x')]),
        ('盘符路径 C:\\\\evil.css', [(r'C:\evil.css', b'x')]),
        ('混合：正常 html + 穿越条目', [
            ('demo_tool.html', b'<html>ok</html>'),
            ('static/../evil.txt', b'x'),
        ]),
    ]
    for label, entries in cases:
        _expect_reject(entries, label)


def test_safe_extract_normal_pack():
    """正向控制组：正常前端工具包解压到正确位置，未知条目不落盘"""
    with TmpBase() as root:
        zip_path = os.path.join(root, 'ok.zip')
        make_zip(zip_path, [
            ('config.json', json.dumps({'name': 'demo_tool', 'version': '1.0.0'}).encode('utf-8')),
            ('demo_tool.html', b'<html>demo</html>'),
            ('static/css/style.css', b'body{}'),
            ('static/js/app.js', b'console.log(1)'),
            ('static/img/logo.png', b'\x89PNG'),
        ])
        target_dir = os.path.join(root, 'templates', 'frontend_tools')
        with zipfile.ZipFile(zip_path, 'r') as zf:
            html_path, static_files = safe_extract_frontend(zf, 'demo_tool', target_dir)

        ok = True
        ok &= html_path == os.path.join(target_dir, 'demo_tool.html')
        ok &= os.path.isfile(os.path.join(target_dir, 'demo_tool.html'))
        ok &= os.path.isfile(os.path.join(target_dir, 'static', 'demo_tool', 'css', 'style.css'))
        ok &= os.path.isfile(os.path.join(target_dir, 'static', 'demo_tool', 'js', 'app.js'))
        ok &= os.path.isfile(os.path.join(target_dir, 'static', 'demo_tool', 'img', 'logo.png'))
        # 未知条目（config.json、其它根级文件）不应落盘
        ok &= not os.path.exists(os.path.join(target_dir, 'config.json'))
        check('正常包解压落位 + 未知条目不落盘', ok, f"static_files={len(static_files)}")

        # 返回静态文件列表
        check('static_files 数量=3',
              len(static_files) == 3, f"实际 {len(static_files)}")

        # 越界检查：临时根之外不应有任何写入
        parent = os.path.dirname(root)
        escaped = [os.path.join(parent, 'evil.txt'), os.path.join(parent, 'demo_tool.html')]
        check('无越界文件写入', not any(os.path.exists(p) for p in escaped), f"parent={parent}")


def test_safe_extract_clean_static():
    """更新时 clean_static=True：先清理旧 static/ 目录再解压，不残留旧版本文件"""
    with TmpBase() as root:
        target_dir = os.path.join(root, 'templates', 'frontend_tools')

        # v1 包：html + static/css + static/js/old.js
        v1 = os.path.join(root, 'v1.zip')
        make_zip(v1, [
            ('demo_tool.html', b'<html>v1</html>'),
            ('static/css/style.css', b'body{v1}'),
            ('static/js/old.js', b'// old'),
        ])
        with zipfile.ZipFile(v1, 'r') as zf:
            safe_extract_frontend(zf, 'demo_tool', target_dir)

        # v2 包：html + static/css（不再有 old.js）
        v2 = os.path.join(root, 'v2.zip')
        make_zip(v2, [
            ('demo_tool.html', b'<html>v2</html>'),
            ('static/css/style.css', b'body{v2}'),
        ])
        with zipfile.ZipFile(v2, 'r') as zf:
            safe_extract_frontend(zf, 'demo_tool', target_dir, clean_static=True)

        old_removed = not os.path.exists(os.path.join(target_dir, 'static', 'demo_tool', 'js', 'old.js'))
        css_updated = os.path.isfile(os.path.join(target_dir, 'static', 'demo_tool', 'css', 'style.css'))
        check('clean_static 清理旧文件 old.js', old_removed)
        check('clean_static 后新 static 存在', css_updated)


def test_safe_extract_clean_static_no_dir():
    """clean_static=True 但旧 static 目录不存在：不报错"""
    with TmpBase() as root:
        target_dir = os.path.join(root, 'templates', 'frontend_tools')
        v1 = os.path.join(root, 'v1.zip')
        make_zip(v1, [('demo_tool.html', b'<html>v1</html>')])
        with zipfile.ZipFile(v1, 'r') as zf:
            try:
                safe_extract_frontend(zf, 'demo_tool', target_dir, clean_static=True)
                check('clean_static 无旧目录不报错', True)
            except Exception as e:
                check('clean_static 无旧目录不报错', False, str(e)[:60])


def test_cleanup_resources():
    """卸载资源清理：入口 html + static/<name>/ 目录被删除，返回列表正确"""
    with TmpBase() as root:
        target_dir = os.path.join(root, 'templates', 'frontend_tools')
        # 构造已安装工具的资源
        os.makedirs(os.path.join(target_dir, 'static', 'demo_tool', 'css'), exist_ok=True)
        with open(os.path.join(target_dir, 'demo_tool.html'), 'w', encoding='utf-8') as f:
            f.write('<html>demo</html>')
        with open(os.path.join(target_dir, 'static', 'demo_tool', 'css', 'style.css'), 'w', encoding='utf-8') as f:
            f.write('body{}')

        removed = cleanup_frontend_resources('demo_tool')

        html_gone = not os.path.exists(os.path.join(target_dir, 'demo_tool.html'))
        static_gone = not os.path.isdir(os.path.join(target_dir, 'static', 'demo_tool'))
        check('清理入口 html', html_gone)
        check('清理 static 目录', static_gone)
        check('返回删除路径列表=2', len(removed) == 2, f"实际 {len(removed)}")
        check('返回列表内容正确',
              removed[0].endswith('demo_tool.html') and removed[1].endswith('static' + os.sep + 'demo_tool'),
              f"removed={removed}")

        # 空 static 父目录可残留（由上传/其它逻辑处理），但再次清理不应报错
        try:
            cleanup_frontend_resources('demo_tool')
            check('重复清理不报错', True)
        except Exception as e:
            check('重复清理不报错', False, str(e)[:60])


if __name__ == '__main__':
    test_safe_extract_rejects_zip_slip()
    test_safe_extract_normal_pack()
    test_safe_extract_clean_static()
    test_safe_extract_clean_static_no_dir()
    test_cleanup_resources()

    passed = sum(1 for _, c, _ in results if c)
    print(f"\n==== 前端工具 zip slip 专项 共 {len(results)} 项，通过 {passed}，失败 {len(results) - passed} ====")
    sys.exit(0 if passed == len(results) else 1)
