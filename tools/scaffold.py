# -*- coding: utf-8 -*-
"""FlaskToolkit 插件脚手架 CLI（v4.10.0 Accessibility，M6）

在本地生成标准插件骨架，产出可直接打包/安装的源目录：
- backend  后端插件包：plugin.json + 主 .py（BasePlugin 子类骨架）+ 可选 templates/static
- frontend 前端工具包：config.json + 入口 .html + 可选 static/

与 tools/package.py（打包签名）、tools/install_plugin.py（不跑框架时手动安装）配合，
完成"生成 → 打包 → 安装"离线闭环；也可用前端后台 /admin/plugins 上传安装。

用法：
  python tools/scaffold.py backend demo_tool [--title 标题] [--category 分类]
                              [--permission user|admin|public] [--author 作者]
                              [--with-templates] [--with-static] [--output DIR]
  python tools/scaffold.py frontend my_tool [--title 标题] [--category 分类]
                               [--permission public|user|admin] [--author 作者]
                               [--with-static] [--output DIR]

退出码：0 = 成功；1 = 参数/IO 错误。
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import global_var
    _FRAMEWORK_VERSION = getattr(global_var, 'FRAMEWORK_VERSION', '4.0.0')
except Exception:
    _FRAMEWORK_VERSION = '4.0.0'

DEFAULT_AUTHOR = 'FlaskToolkit User'
VALID_PERMISSIONS = ('public', 'user', 'admin')
_IDENT_RE = re.compile(r'^[a-z][a-z0-9_]*$')

BACKEND_PY_TEMPLATE = '''# -*- coding: utf-8 -*-
"""
{title}（{name}）
========================================
由 tools/scaffold.py 生成的插件骨架（v4.10.0 M6）。

包含：
1. 三层权限路由：public（游客）/ user（登录）/ admin（管理员）
2. 生命周期钩子：on_load / on_shutdown / on_unload / on_uninstall
3. 配置持久化：load_config / save_config（存于 plugins/configs/{name}.json）
4. 页面路由：page=True 渲染命名空间模板 templates/plugins/{name}/

安装后（路径均为插件前缀 /api/{name} 下）：
- GET  /public   游客可访问
- GET  /user     登录后可访问
- GET  /admin    仅管理员
- 页面 /plugin/{name}            （插件索引页，由框架自动生成）
- 子页 /plugin/{name}/about      （页面路由示例，见 routes 中 page=True 项）
"""
import json
from typing import List, Dict

from flask import request

from plugins.base_plugin import BasePlugin, permission as permission_required


class {ClassName}(BasePlugin):
    name = "{name}"
    title = "{title}"
    description = "{description}"
    version = "1.0.0"
    author = "{author}"
    category = "{category}"
    permission = "{permission}"
    require_framework_version = "{framework_version}"

    # 默认配置（可被 plugins/configs/{name}.json 覆盖）
    DEFAULT_CONFIG = {{
        "greeting": "你好，FlaskToolkit！",
        "visits": 0,
    }}

    # ---------------- 生命周期钩子 ----------------
    def on_load(self):
        """插件加载完成后调用：初始化配置、注册定时任务等"""
        self.load_config()
        if not self.config:
            self.config = dict(self.DEFAULT_CONFIG)
            self.save_config()
        self.logger.info("{name} 加载完成，greeting={{{{ self.config.get('greeting') }}}}")

    def on_shutdown(self):
        """服务停止前调用：清理资源、持久化状态"""
        self.logger.info("{name} 正在停止，执行清理...")

    def on_unload(self):
        """插件被卸载（文件删除）前调用"""
        self.logger.info("{name} 被卸载")

    def on_uninstall(self):
        """插件被正式卸载时调用（可清理本插件产生的数据）"""
        self.logger.info("{name} 已卸载，清理示例数据")

    # ---------------- 路由 ----------------
    @property
    def routes(self) -> List[Dict]:
        return [
            {{
                "path": "/public",
                "name": "游客接口（public 权限）",
                "methods": ["GET"],
                "params": [
                    {{"name": "name", "type": "string", "required": False, "default": "游客", "description": "称呼"}}
                ],
                "view_func": self.api_public,
            }},
            {{
                "path": "/user",
                "name": "登录用户接口（user 权限）",
                "methods": ["GET"],
                "params": [],
                "view_func": self.api_user,
            }},
            {{
                "path": "/admin",
                "name": "管理员接口（admin 权限）",
                "methods": ["GET"],
                "params": [],
                "view_func": self.api_admin,
            }},
            {{
                "path": "/about", "name": "关于本插件", "methods": ["GET"],
                "page": True, "template": "about.html", "view_func": self.page_about,
            }},
        ]

    # ---------------- 视图函数 ----------------
    @permission_required("public")
    def api_public(self):
        """游客可访问：演示 public 权限"""
        name = (request.args.get('name') or '').strip() or '游客'
        return {{"code": 200, "message": "public 接口可访问", "data": {{"greeting": "你好，{{0}}！".format(name)}}}}

    @permission_required("user")
    def api_user(self):
        """登录用户可访问：演示 user 权限"""
        return {{"code": 200, "message": "user 接口可访问", "data": {{"tips": "登录后可用"}}}}

    @permission_required("admin")
    def api_admin(self):
        """仅管理员可访问：演示 admin 权限"""
        return {{"code": 200, "message": "admin 接口可访问", "data": {{"who": "管理员"}}}}

    def page_about(self):
        """页面路由示例：返回 dict → 框架渲染命名空间模板 templates/plugins/{name}/about.html"""
        return {{
            "title": "关于本插件",
            "content": "{description}",
        }}
'''

BACKEND_PLUGIN_JSON_TEMPLATE = '''{{
  "name": "{name}",
  "title": "{title}",
  "version": "1.0.0",
  "author": "{author}",
  "category": "{category}",
  "description": "{description}",
  "permission": "{permission}",
  "require_framework_version": "{framework_version}",
  "capabilities": []
}}
'''

BACKEND_INDEX_HTML_TEMPLATE = '''{{% extends "plugins/{name}/base.html" %}}

{{% block content %}}
<div class="card">
  <h2>{{{{ title }}}}</h2>
  <p>{{{{ content }}}}</p>
  <p><a href="/plugin/{name}/about">关于本插件（子页面路由示例）</a></p>
</div>
{{% endblock %}}
'''

BACKEND_BASE_HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{{{{ title }}}} - {title}</title>
  <link rel="stylesheet" href="/static/plugins/{name}/style.css">
</head>
<body>
  <header>
    <h1>{{{{ title }}}}</h1>
    <nav><a href="/plugin/{name}">首页</a></nav>
  </header>
  <main>
    {{% block content %}}{{% endblock %}}
  </main>
  <footer>由 tools/scaffold.py 生成</footer>
</body>
</html>
'''

BACKEND_STATIC_CSS = '''/* {title} 插件静态资源示例（安装后位于 /static/plugins/{name}/style.css） */
body {{ font-family: system-ui, sans-serif; margin: 0; background: #f5f6f8; color: #222; }}
header {{ background: #2563eb; color: #fff; padding: 12px 24px; }}
header h1 {{ margin: 0; font-size: 20px; }}
header nav a {{ color: #fff; margin-left: 16px; text-decoration: none; }}
main {{ max-width: 860px; margin: 24px auto; padding: 0 16px; }}
.card {{ background: #fff; border: 1px solid #e2e4e8; border-radius: 8px; padding: 16px 20px; }}
footer {{ text-align: center; color: #888; padding: 24px; font-size: 13px; }}
'''

FRONTEND_CONFIG_TEMPLATE = '''{{
  "name": "{name}",
  "title": "{title}",
  "version": "1.0.0",
  "author": "{author}",
  "category": "{category}",
  "description": "{description}",
  "permission": "{permission}",
  "require_framework_version": "{framework_version}"
}}
'''

FRONTEND_HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="/frontend-static/{name}/style.css">
</head>
<body>
  <main class="wrap">
    <h1>{title}</h1>
    <p class="desc">{description}</p>
    <section class="card">
      <p>这是一个由 tools/scaffold.py 生成的前端工具骨架。</p>
      <button id="btn">点击试试</button>
      <p id="out" class="out"></p>
    </section>
  </main>
  <script>
    document.getElementById('btn').addEventListener('click', function () {{
      document.getElementById('out').textContent = 'Hello, FlaskToolkit! (' + new Date().toLocaleString() + ')';
    }});
  </script>
</body>
</html>
'''

FRONTEND_STATIC_CSS = '''/* {title} 前端工具静态资源示例（安装后位于 /frontend-static/{name}/style.css） */
body {{ font-family: system-ui, sans-serif; margin: 0; background: #f5f6f8; color: #222; }}
.wrap {{ max-width: 720px; margin: 48px auto; padding: 0 16px; }}
.wrap h1 {{ font-size: 26px; }}
.desc {{ color: #666; }}
.card {{ background: #fff; border: 1px solid #e2e4e8; border-radius: 10px; padding: 20px 24px; }}
.card button {{ background: #2563eb; color: #fff; border: 0; border-radius: 6px; padding: 8px 18px; cursor: pointer; }}
.out {{ margin-top: 12px; color: #2563eb; }}
'''

NOTICE = '''下一步（离线闭环）：
  1. 打包：python tools/package.py pack ./{name} -o {name}.zip --type {kind}
     （需签名时追加 --sign private.pem --signer "昵称"）
  2. 安装（不跑框架）：python tools/install_plugin.py {kind} {name}.zip
     或运行框架后在前端后台 /admin/plugins 上传安装
'''


def _validate_name(name: str) -> str:
    """插件名约束：小写字母开头，仅 [a-z0-9_]（与框架 secure_filename 语义一致）"""
    if not _IDENT_RE.match(name):
        raise ValueError(f"插件名不合法: {name!r}（需小写字母开头，仅含 [a-z0-9_]）")
    return name


def _validate_permission(permission: str) -> str:
    if permission not in VALID_PERMISSIONS:
        raise ValueError(f"permission 不合法: {permission!r}（可选 {', '.join(VALID_PERMISSIONS)}）")
    return permission


def _safe_json_escape(text: str) -> str:
    """JSON 转义后用于模板插值（防引号/换行破坏生成文件）"""
    return json.dumps(text, ensure_ascii=False)[1:-1]


def _write(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    print(f"  已生成: {path}")


def _class_name(name: str) -> str:
    return ''.join(part.capitalize() for part in name.split('_'))


def cmd_backend(args):
    name = _validate_name(args.name)
    permission = _validate_permission(args.permission)
    out = os.path.abspath(os.path.join(args.output, name))
    if os.path.exists(out) and os.listdir(out):
        raise ValueError(f"目标目录已存在且非空: {out}")

    title = args.title or f"示例：{name}"
    description = args.description or f"{title}（由 tools/scaffold.py 生成的插件骨架）"
    author = args.author or DEFAULT_AUTHOR

    print(f"生成后端插件骨架 → {out}")
    _write(os.path.join(out, 'plugin.json'),
           BACKEND_PLUGIN_JSON_TEMPLATE.format(
               name=name, title=_safe_json_escape(title), author=_safe_json_escape(author),
               category=_safe_json_escape(args.category or '示例'), description=_safe_json_escape(description),
               permission=permission, framework_version=_FRAMEWORK_VERSION))
    _write(os.path.join(out, f'{name}.py'),
           BACKEND_PY_TEMPLATE.format(
               name=name, ClassName=_class_name(name), title=_safe_json_escape(title),
               description=_safe_json_escape(description), author=_safe_json_escape(author),
               category=_safe_json_escape(args.category or '示例'), permission=permission,
               framework_version=_FRAMEWORK_VERSION))

    if args.with_templates:
        tpl_dir = os.path.join(out, 'templates', name)
        _write(os.path.join(tpl_dir, 'base.html'),
               BACKEND_BASE_HTML_TEMPLATE.format(name=name, title=_safe_json_escape(title)))
        _write(os.path.join(tpl_dir, 'index.html'),
               BACKEND_INDEX_HTML_TEMPLATE.format(name=name))
        _write(os.path.join(tpl_dir, 'about.html'),
               '{{% extends "plugins/{name}/base.html" %}}\n\n{{% block content %}}\n'
               '<div class="card"><h2>{{{{ content }}}}</h2></div>\n{{% endblock %}}\n'.format(name=name))
    if args.with_static:
        _write(os.path.join(out, 'static', 'style.css'),
               BACKEND_STATIC_CSS.format(name=name, title=_safe_json_escape(title)))

    print()
    print(NOTICE.format(name=name, kind='backend'))
    print(f"提示：模板/静态资源目录为可选；不生成时插件仍可运行（仅 API）。")


def cmd_frontend(args):
    name = _validate_name(args.name)
    permission = _validate_permission(args.permission)
    out = os.path.abspath(os.path.join(args.output, name))
    if os.path.exists(out) and os.listdir(out):
        raise ValueError(f"目标目录已存在且非空: {out}")

    title = args.title or f"示例：{name}"
    description = args.description or f"{title}（由 tools/scaffold.py 生成的前端工具骨架）"
    author = args.author or DEFAULT_AUTHOR

    print(f"生成前端工具骨架 → {out}")
    _write(os.path.join(out, 'config.json'),
           FRONTEND_CONFIG_TEMPLATE.format(
               name=name, title=_safe_json_escape(title), author=_safe_json_escape(author),
               category=_safe_json_escape(args.category or '示例'), description=_safe_json_escape(description),
               permission=permission, framework_version=_FRAMEWORK_VERSION))
    _write(os.path.join(out, f'{name}.html'),
           FRONTEND_HTML_TEMPLATE.format(
               name=name, title=_safe_json_escape(title), description=_safe_json_escape(description)))
    if args.with_static:
        _write(os.path.join(out, 'static', 'style.css'),
               FRONTEND_STATIC_CSS.format(name=name, title=_safe_json_escape(title)))

    print()
    print(NOTICE.format(name=name, kind='frontend'))
    print(f"提示：前端工具必须提供 {name}.html 入口；static/ 可选（资源以 /frontend-static/{name}/ 前缀引用）。")


def main():
    ap = argparse.ArgumentParser(description='FlaskToolkit 插件脚手架 CLI（生成 backend/frontend 骨架）')
    sub = ap.add_subparsers(dest='kind', required=True, help='backend=后端插件 / frontend=前端工具')

    for kind, desc in (('backend', '后端插件包（plugin.json + 主 .py + 可选 templates/static）'),
                       ('frontend', '前端工具包（config.json + 入口 .html + 可选 static/）')):
        p = sub.add_parser(kind, help=desc)
        p.add_argument('name', help='插件/工具名（小写字母开头，仅 [a-z0-9_]）')
        p.add_argument('--title', help='显示标题（缺省 示例：<name>）')
        p.add_argument('--description', help='描述（缺省自动生成）')
        p.add_argument('--category', default='示例', help='分类（缺省 示例）')
        p.add_argument('--permission', default='user',
                       help=f"默认权限（缺省 user；可选 {', '.join(VALID_PERMISSIONS)}）")
        p.add_argument('--author', default=DEFAULT_AUTHOR, help=f'作者（缺省 {DEFAULT_AUTHOR}）')
        p.add_argument('--output', default='.', help='输出目录（缺省当前目录，骨架生成到 <output>/<name>/）')
        if kind == 'backend':
            p.add_argument('--with-templates', action='store_true', help='生成 templates/<name>/ 页面模板骨架')
            p.add_argument('--with-static', action='store_true', help='生成 static/ 静态资源骨架')
        else:
            p.add_argument('--with-static', action='store_true', help='生成 static/ 静态资源骨架')

    args = ap.parse_args()
    try:
        if args.kind == 'backend':
            cmd_backend(args)
        else:
            cmd_frontend(args)
    except ValueError as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        print(f"错误：生成失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
