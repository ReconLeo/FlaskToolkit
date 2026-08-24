# -*- coding: utf-8 -*-
"""
插件包（.zip）解析与解压工具

插件包格式（类比前端工具包）：
    <plugin_name>.zip
    ├── plugin.json          # 描述文件（必填，类比前端工具的 config.json）
    ├── <plugin_name>.py     # 主插件文件（必填，文件名需与 plugin.json 的 name 一致）
    ├── templates/           # 可选：插件专属模板 → 解压到 templates/plugins/
    └── static/              # 可选：插件静态资源 → 解压到 templates/plugins/static/<name>/

解压安全：内置 zip slip（路径穿越）防护，仅允许解压到项目内的合法位置。
"""
import ast
import json
import logging
import os
import shutil
import zipfile

import global_var

logger = logging.getLogger('flask.app')

PLUGIN_PACK_DESC_FILE = 'plugin.json'

# 插件可声明元信息字段（plugin.json 与插件类属性两处均可能出现）
META_FIELDS = (
    'name', 'version', 'title', 'author', 'permission',
    'category', 'description', 'dependencies',
    'require_framework_version',
)
# 参与“冲突拒绝”比对的字段（name 单独走强制一致校验）
COMPARE_FIELDS = (
    'version', 'title', 'author', 'permission',
    'category', 'description', 'dependencies',
    'require_framework_version',
)


def parse_plugin_pack(zip_path: str) -> dict:
    """
    解析插件包并做“描述一致性”对齐校验（plugin.json 与插件类属性两处信息）。

    规则（v4.1）：
    1. plugin.json 必须存在且为合法 JSON，name 非空；
    2. name 三处一致：plugin.json.name == 主 .py 文件名 == 插件类 name（AST 可提取时）；
    3. 冲突字段拒绝：version/title/author/permission/category/description/dependencies
       在 plugin.json 与类属性同时声明且不一致 → 拒绝上传并报告具体冲突字段；
    4. 缺失补全：plugin.json 缺失的字段回退到类属性（version 缺失用类兜底并告警）。

    返回“对齐后”的描述 dict（plugin.json 为准，缺失字段已用类属性补齐）。
    """
    try:
        zf = zipfile.ZipFile(zip_path, 'r')
    except zipfile.BadZipFile:
        raise ValueError("无效的 zip 文件")
    with zf:
        names = [n.replace('\\', '/') for n in zf.namelist()]
        if PLUGIN_PACK_DESC_FILE not in names:
            raise ValueError(
                f"插件包缺少描述文件 {PLUGIN_PACK_DESC_FILE}"
                "（类比前端工具包的 config.json，需声明 name/version 等元信息）"
            )
        try:
            desc = json.loads(zf.read(PLUGIN_PACK_DESC_FILE).decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ValueError("plugin.json 描述文件格式错误（需为合法 JSON）")
        if not isinstance(desc, dict):
            raise ValueError("plugin.json 内容必须为 JSON 对象")
        name = (desc.get('name') or '').strip()
        if not name:
            raise ValueError("plugin.json 缺少必填字段: name")
        main_py = f"{name}.py"
        if main_py not in names:
            raise ValueError(
                f"插件包缺少主插件文件: {main_py}"
                "（主 .py 文件名需与 plugin.json 的 name 一致）"
            )

        # ---- 描述一致性对齐校验（AST 静态解析主 .py，不执行代码） ----
        py_source = zf.read(main_py).decode('utf-8', errors='replace')
        class_meta = extract_class_meta_from_py(py_source)

        # 1) name 三处一致：plugin.json.name == .py 文件名（已保证）== 类 name（AST 可提取时）
        cls_name = class_meta.get('name')
        if cls_name and cls_name != name:
            raise ValueError(
                f"plugin.json 的 name 与插件类 name 不一致"
                f"（plugin.json: {name}，类: {cls_name}）"
            )

        # 2) 冲突字段拒绝：两处同时声明且不一致
        conflicts = []
        for f in COMPARE_FIELDS:
            if f in desc and f in class_meta and desc[f] != class_meta[f]:
                conflicts.append(f)
        if conflicts:
            raise ValueError(
                f"plugin.json 与插件类属性冲突字段: {', '.join(conflicts)}"
                "（请保持 plugin.json 与插件类属性一致后重新打包）"
            )

        # 3) 缺失补全：plugin.json 缺失字段回退类属性
        aligned = dict(desc)
        for f in META_FIELDS:
            if f not in aligned and f in class_meta:
                aligned[f] = class_meta[f]
        if 'version' not in aligned and 'version' in class_meta:
            logger.warning(
                f"plugin.json 未声明 version，已回退插件类版本 {class_meta['version']}",
                extra={'plugin': 'system'},
            )

        # 4) 最低框架版本校验（可选字段：声明后须满足，否则拒绝安装/更新）
        if 'require_framework_version' in aligned:
            ok, msg = check_framework_version(aligned['require_framework_version'])
            if not ok:
                raise ValueError(msg)

        return aligned


def _const_eval(node) -> any:
    """AST 常量求值：字符串/数字/布尔/列表/元组字面量；无法静态求值返回 None"""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        vals = []
        for elt in node.elts:
            v = _const_eval(elt)
            if v is None:
                return None
            vals.append(v)
        return vals
    return None


def extract_class_meta_from_py(py_source: str) -> dict:
    """
    静态提取插件主文件中继承 BasePlugin 的类元信息（AST 解析，不执行代码）。
    仅提取类体中的直接赋值（含类型注解），如 `name = "xxx"` / `version = "1.0.1"`
    / `dependencies = ["auth"]`。
    返回 dict（可能为空），用于上传/更新时的对齐校验。
    """
    try:
        tree = ast.parse(py_source)
    except SyntaxError:
        return {}

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
        if 'BasePlugin' not in bases:
            continue

        meta = {}
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                targets = [t for t in stmt.targets if isinstance(t, ast.Name)]
                if not targets:
                    continue
                target = targets[0]
                if target.id not in META_FIELDS:
                    continue
                value = _const_eval(stmt.value)
                if value is not None:
                    meta[target.id] = value
            elif isinstance(stmt, ast.AnnAssign):
                if not isinstance(stmt.target, ast.Name) or stmt.target.id not in META_FIELDS:
                    continue
                value = _const_eval(stmt.value)
                if value is not None:
                    meta[stmt.target.id] = value
        return meta  # 取第一个继承 BasePlugin 的类
    return {}


def extract_plugin_pack(zip_path: str, plugin_name: str, meta_override: dict = None,
                        clean_old: bool = True) -> dict:
    """
    安全解压插件包到对应位置（防 zip slip 路径穿越）：
    - 根目录 .py 文件     → plugins/
    - templates/ 目录文件 → templates/plugins/
    - static/ 目录文件    → templates/plugins/static/<plugin_name>/

    安装/更新时把“引入的全部文件”相对路径清单写入 plugins/<plugin_name>.json 的
    installed_files 字段；clean_old=True 时先按旧清单删除旧版本引入的文件
    （解决多 .py 插件包卸载/更新时辅助模块残留问题）。

    返回解压结果 dict: {'main': 主文件路径, 'py': [...], 'templates': [...], 'static': [...], 'meta': None}
    """
    base = global_var.BASE_DIR
    # 0. 更新场景：先按旧 installed_files 清单删除旧版本引入的文件（容错，文件不存在则忽略）
    if clean_old:
        _delete_installed_files(plugin_name)

    result = {'main': None, 'py': [], 'templates': [], 'static': [], 'meta': None}
    meta_dest = None
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for member in zf.namelist():
            # zip 内路径统一用 '/' 分隔（不能用 os.path.normpath，Windows 下会把 '/' 转成 '\\'）
            normalized = member.replace('\\', '/')
            if normalized.endswith('/'):
                continue  # 目录条目

            # ---- zip slip 防护：拒绝 .. / 绝对路径 / 盘符路径 ----
            parts = normalized.split('/')
            if '..' in parts:
                raise ValueError(f"插件包包含非法路径（存在路径穿越风险）: {member}")
            if normalized.startswith('/') or (len(normalized) >= 2 and normalized[1] == ':'):
                raise ValueError(f"插件包包含绝对路径（非法）: {member}")

            if normalized == PLUGIN_PACK_DESC_FILE:
                # 描述文件 → plugins/<plugin_name>.json（作为插件包元信息真相来源，循环后统一落盘）
                meta_dest = os.path.join(base, 'plugins', f"{plugin_name}.json")
                result['meta'] = meta_dest
            elif len(parts) == 1 and parts[0].endswith('.py'):
                # 根目录 .py → plugins/
                dest = os.path.join(base, 'plugins', parts[0])
                _write_member(zf, member, dest)
                if parts[0] == f"{plugin_name}.py":
                    result['main'] = dest
                result['py'].append(dest)
            elif parts[0] == 'templates':
                # 模板 → templates/plugins/
                dest = os.path.join(base, 'templates', 'plugins', *parts[1:])
                _write_member(zf, member, dest)
                result['templates'].append(dest)
            elif parts[0] == 'static':
                # 静态资源 → templates/plugins/static/<plugin_name>/
                dest = os.path.join(base, 'templates', 'plugins', 'static', plugin_name, *parts[1:])
                _write_member(zf, member, dest)
                result['static'].append(dest)
            else:
                logger.warning(f"插件包包含未知条目，已忽略: {member}", extra={'plugin': 'system'})

        # 统一落盘描述文件（合并 installed_files 安装文件清单）
        if meta_dest:
            if meta_override is not None:
                meta = dict(meta_override)
            else:
                try:
                    meta = json.loads(zf.read(PLUGIN_PACK_DESC_FILE).decode('utf-8'))
                except Exception:
                    meta = {}
            _all_files = [meta_dest] + result['py'] + result['templates'] + result['static']
            meta['installed_files'] = [
                os.path.relpath(p, base).replace(os.sep, '/') for p in _all_files
            ]
            _write_text(meta_dest, json.dumps(meta, ensure_ascii=False, indent=2))
    return result


def _write_text(dest: str, text: str):
    """写入文本文件（自动建目录）"""
    dest_abs = os.path.abspath(dest)
    base = os.path.abspath(global_var.BASE_DIR)
    if not (dest_abs == base or dest_abs.startswith(base + os.sep)):
        raise ValueError(f"插件包解压目标超出项目目录: {dest}")
    os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
    with open(dest_abs, 'w', encoding='utf-8') as out:
        out.write(text)


def _write_member(zf: zipfile.ZipFile, member: str, dest: str):
    """从 zip 安全写入单个文件（自动建目录；写入前二次校验目标在项目目录内）"""
    base = os.path.abspath(global_var.BASE_DIR)
    dest_abs = os.path.abspath(dest)
    if not (dest_abs == base or dest_abs.startswith(base + os.sep)):
        raise ValueError(f"插件包解压目标超出项目目录: {dest}")
    os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
    with zf.open(member) as src, open(dest_abs, 'wb') as out:
        shutil.copyfileobj(src, out)


def _read_installed_files(plugin_name: str) -> list:
    """读取插件描述文件中的安装文件清单（相对路径），无则返回空列表"""
    meta_file = os.path.join(global_var.BASE_DIR, 'plugins', f"{plugin_name}.json")
    if not os.path.isfile(meta_file):
        return []
    try:
        with open(meta_file, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        return [x for x in meta.get('installed_files', []) if isinstance(x, str)]
    except Exception:
        return []


def _prune_empty_dirs(base: str, start_dirs: list):
    """从给定目录向上逐级删除空目录（不越过项目根）"""
    for d in start_dirs:
        cur = d
        while cur and os.path.isdir(cur) and cur != base and cur.startswith(base + os.sep):
            try:
                os.rmdir(cur)  # 仅删除空目录
                cur = os.path.dirname(cur)
            except OSError:
                break


def _delete_installed_files(plugin_name: str) -> list:
    """按安装清单删除插件引入的文件（相对路径，安全校验防穿越），并清理空目录。
    返回删除路径列表；无清单时返回 []。"""
    base = global_var.BASE_DIR
    removed = []
    installed = _read_installed_files(plugin_name)
    if not installed:
        return removed
    for rel in installed:
        p = os.path.abspath(os.path.join(base, rel.replace('/', os.sep)))
        if not (p == base or p.startswith(base + os.sep)):
            continue  # 防御：清单路径必须在本项目内
        try:
            if os.path.isfile(p):
                os.remove(p)
                removed.append(p)
            elif os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
                removed.append(p)
        except OSError:
            pass
    # 清理因删除产生的空目录
    _prune_empty_dirs(base, [os.path.dirname(p) for p in removed])
    return removed


def cleanup_plugin_resources(plugin_name: str) -> list:
    """
    删除插件关联的文件（卸载时调用）。
    优先按安装清单（plugins/<name>.json 的 installed_files）删除全部引入文件
    （主 .py + 辅助模块 + 模板 + 静态资源），并清理空目录；
    老插件（无清单）回退到按命名约定删除主模板与静态目录。
    返回删除路径列表。
    """
    base = global_var.BASE_DIR
    # 1. 有安装清单：按清单删除（覆盖多 .py 插件包的辅助模块）
    if _read_installed_files(plugin_name):
        return _delete_installed_files(plugin_name)

    # 2. 回退：无清单的老插件（按命名约定删除）
    removed = []
    meta_file = os.path.join(base, 'plugins', f"{plugin_name}.json")
    if os.path.isfile(meta_file):
        os.remove(meta_file)
        removed.append(meta_file)
    main_tpl = os.path.join(base, 'templates', 'plugins', f"{plugin_name}.html")
    if os.path.isfile(main_tpl):
        os.remove(main_tpl)
        removed.append(main_tpl)
    static_dir = os.path.join(base, 'templates', 'plugins', 'static', plugin_name)
    if os.path.isdir(static_dir):
        shutil.rmtree(static_dir)
        removed.append(static_dir)
    return removed


def check_framework_version(require: str, framework: str = None) -> tuple:
    """
    校验插件的最低框架版本要求（可选字段，未声明则放行）。
    :return: (ok, message)；ok=False 时 message 说明拒绝原因。
    """
    if not require:
        return True, ''
    framework = framework or global_var.FRAMEWORK_VERSION
    if compare_versions(str(require), str(framework)) > 0:
        return False, (
            f"插件要求框架最低版本 {require}，当前框架版本 {framework}"
        )
    return True, ''


def compare_versions(v_new: str, v_old: str) -> int:
    """
    比较版本号：返回 1（新>旧）、0（相等）、-1（新<旧）。
    支持点分数字（如 '1.10.2'）与 'v' 前缀。
    """
    def _split(v):
        v = str(v).strip().lstrip('vV')
        nums = []
        for seg in v.replace('-', '.').split('.'):
            if seg.isdigit():
                nums.append(int(seg))
            else:
                nums.append(0)
        # 补齐长度便于比较
        while len(nums) < 3:
            nums.append(0)
        return nums

    a, b = _split(v_new), _split(v_old)
    for x, y in zip(a, b):
        if x > y:
            return 1
        if x < y:
            return -1
    return 0
