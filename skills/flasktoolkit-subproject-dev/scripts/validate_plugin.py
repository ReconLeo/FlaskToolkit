#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
validate_plugin.py —— FlaskToolkit 子项目插件静态校验器
=======================================================
安装前自检，覆盖"示例插件更新注意事项"要点：
  1. plugin.json 与主 .py 插件类属性两处一致（冲突 → 上传 400）
  2. name 三处一致（plugin.json.name == 主 .py 文件名 == 类 name）
  3. require_framework_version ≤ 当前框架版本
  4. capabilities 声明合法（域识别 + 已知域校验）
  5. 全仓 LF 行尾（禁止 CRLF / \\r\\r\\n）
  6. 源码目录不含 __pycache__ / .pyc 编译产物

用法：
  python validate_plugin.py <src_dir>
      [--framework-root <框架根>]   # 从 global_var.py 读取当前框架版本
      [--current-version <x.y.z>]   # 或直接指定当前框架版本
      [--name <插件名>]             # 主 .py 文件名与插件名不一致时手动指定

退出码：0 全部通过 / 1 有错误 / 2 有警告（仅提示）。

路径一律不硬编码；框架根等由用户传入或走环境变量 FTK_FRAMEWORK_PATH。
"""
import argparse
import ast
import json
import os
import re
import sys

# 与框架 core/capabilities.py KNOWN_DOMAINS 对齐的已知能力域
KNOWN_DOMAINS = {
    "filesystem", "network", "webhook", "process", "scheduler",
    "database", "device", "framework", "env", "storage",
}
# 参与描述一致性冲突比对的字段（对齐框架 plugin_pack 的 META_FIELDS）
META_FIELDS = [
    "version", "title", "author", "permission", "category",
    "description", "dependencies", "require_framework_version",
]


def parse_versions(s: str):
    """简化点分版本 → 数值元组（忽略预发布权重，仅数值段）"""
    s = str(s).strip().lower()
    if s.startswith("v"):
        s = s[1:]
    nums = re.findall(r"\d+", s)
    return tuple(int(n) for n in nums) if nums else ()


def extract_class_attrs(tree):
    """用 AST 解析主 .py 中插件类的字面量类属性（不执行插件代码）"""
    attrs = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if any(base.id == "BasePlugin" for base in node.bases if isinstance(base, ast.Name)):
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name) and isinstance(item.value, ast.Constant):
                            attrs[target.id] = item.value.value
    return attrs


def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def check_lf(src_dir, problems, warnings):
    """检查源码目录文本文件统一 LF，不含 CRLF / \\r\\r\\n"""
    text_exts = {".py", ".json", ".html", ".css", ".js", ".md", ".yaml", ".yml"}
    for root, dirs, files in os.walk(src_dir):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git", "node_modules"}]
        for fn in files:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in text_exts:
                continue
            path = os.path.join(root, fn)
            try:
                with open(path, "rb") as f:
                    data = f.read()
            except OSError:
                continue
            if b"\r" in data:
                problems.append(f"非 LF 行尾: {os.path.relpath(path, src_dir)}")


def check_pycache(src_dir, problems):
    for root, dirs, files in os.walk(src_dir):
        if "__pycache__" in root.split(os.sep):
            for fn in files:
                if fn.endswith(".pyc"):
                    problems.append(
                        f"发现编译产物: {os.path.relpath(os.path.join(root, fn), src_dir)}")


def main():
    ap = argparse.ArgumentParser(description="FlaskToolkit 插件静态校验器")
    ap.add_argument("src_dir", help="插件源目录（含 plugin.json 与主 .py）")
    ap.add_argument("--framework-root", default=os.environ.get("FTK_FRAMEWORK_PATH", ""),
                    help="框架根目录（用于读取当前版本）")
    ap.add_argument("--current-version", default="",
                    help="当前框架版本（点分），未提供则尝试从框架根读取")
    ap.add_argument("--name", default="", help="插件名（缺省取 plugin.json.name）")
    args = ap.parse_args()

    src_dir = os.path.abspath(args.src_dir)
    problems, warnings = [], []

    # 定位 plugin.json 与主 .py
    pj = os.path.join(src_dir, "plugin.json")
    if not os.path.exists(pj):
        print(f"[错误] 缺少 plugin.json: {pj}")
        sys.exit(1)
    meta = load_json(pj)

    plugin_name = args.name or meta.get("name")
    if not plugin_name:
        print("[错误] plugin.json 缺少 name 字段")
        sys.exit(1)
    main_py = os.path.join(src_dir, plugin_name + ".py")

    # ---- 1. 主 .py 存在性 + name 三处一致 ----
    if not os.path.exists(main_py):
        problems.append(f"主插件文件不存在（应为 {plugin_name}.py，与 plugin.json.name 一致）")
    else:
        with open(main_py, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        attrs = extract_class_attrs(tree)
        if "name" in attrs and attrs["name"] != plugin_name:
            problems.append(f"类 name({attrs['name']!r}) 与 plugin.json.name({plugin_name!r}) 不一致")
        # ---- 2. 字段一致性（两处声明且不一致 → 400）----
        for field in META_FIELDS:
            jv, av = meta.get(field), attrs.get(field)
            if jv is not None and av is not None and jv != av:
                problems.append(f"冲突字段 {field}: plugin.json={jv!r} 类属性={av!r}")

    # ---- 3. require_framework_version ≤ 当前框架 ----
    req = meta.get("require_framework_version")
    current = args.current_version
    if not current and args.framework_root:
        gv = os.path.join(args.framework_root, "global_var.py")
        if os.path.exists(gv):
            with open(gv, "r", encoding="utf-8") as f:
                m = re.search(r"FRAMEWORK_VERSION\s*=\s*[\"']([^\"']+)[\"']", f.read())
                if m:
                    current = m.group(1)
    if req:
        if not current:
            warnings.append(f"无法确定当前框架版本，跳过 require_framework_version 校验")
        elif parse_versions(req) > parse_versions(current):
            problems.append(f"require_framework_version({req}) 高于当前框架版本({current})，无法安装")

    # ---- 4. capabilities 合法性 ----
    for cap in meta.get("capabilities", []) or []:
        domain = cap.split(":", 1)[0]
        if domain not in KNOWN_DOMAINS:
            warnings.append(f"未知能力域: {cap}")

    # ---- 5 / 6. LF 与 pycache ----
    check_lf(src_dir, problems, warnings)
    check_pycache(src_dir, problems)

    # ---- 输出 ----
    for w in warnings:
        print(f"[警告] {w}")
    for p in problems:
        print(f"[错误] {p}")
    print(f"通过：plugin.json 元信息字段 = {sorted(k for k in meta if k in META_FIELDS + ['name','capabilities'])}")
    if problems:
        print(f"结果：{len(problems)} 个错误，{len(warnings)} 个警告 → 失败")
        sys.exit(1)
    print(f"结果：通过（{len(warnings)} 个警告）")
    sys.exit(0)


if __name__ == "__main__":
    main()
