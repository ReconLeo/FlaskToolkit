# -*- coding: utf-8 -*-
"""FlaskToolkit 翻译状态工具（v4.15.4）

扫描 locales/ 语言包，以 en.json 为完整参考基准，报告各语言翻译进度与贡献者信息，
并可基于 en.json 模板创建新语言包，鼓励 GitHub 翻译贡献。

元信息字段约定（固定前缀 ``__``，不参与翻译对照）：
- ``__name__``        语言自称（如 "English"、"简体中文"），供 available_languages 展示
- ``__contributors``  贡献者数组，每项 ``{"name": "…", "url": "…"}``（url 可选）
中文（zh-CN）为源语言：key 即中文原文，缺省回退返回原文，视为完整覆盖。

内置语言 en（参考基准）与 zh-CN（源语言）不可创建/修改；其它语言可自行创建。

用法：
  python tools/i18n_status.py                          # 查看全部语言包翻译状态
  python tools/i18n_status.py en                       # 仅查看指定语言包
  python tools/i18n_status.py --json                   # JSON 输出（供脚本/CI 使用）
  python tools/i18n_status.py --check                  # 校验全部语言包 JSON 合法
  python tools/i18n_status.py --create fr --name 法语  # 基于 en.json 创建新语言包
"""
import argparse
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALES = os.path.join(BASE, 'locales')
META_PREFIX = '__'          # 元信息字段固定前缀
REFERENCE = 'en.json'       # 完整参考语言包
SOURCE_LANG = 'zh-CN'       # 源语言（中文原文即 key）
BUILTIN = ('en', 'zh-CN')    # 内置语言：不可创建/修改
_LANG_RE = re.compile(r'^[A-Za-z0-9-]+$')

try:
    import global_var
    GITHUB_URL = getattr(global_var, 'PROJECT_GITHUB', '') or 'https://github.com/ReconLeo/FlaskToolkit'
except Exception:
    GITHUB_URL = 'https://github.com/ReconLeo/FlaskToolkit'

_GITHUB_TIP = (
    '欢迎贡献翻译！翻译完成后在 locales/<lang>.json 的 __contributors 中填写你的信息，'
    '并在 GitHub 发起 PR 或 issue：\n'
    f'  {GITHUB_URL}'
)


def _load(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _content_keys(data):
    """非元信息字段（可翻译 key）集合。"""
    if not isinstance(data, dict):
        return set()
    return {k for k in data if not k.startswith(META_PREFIX)}


def _contributors(data):
    """读取 __contributors，返回规范化的 [{name,url}] 列表。"""
    raw = (data or {}).get('__contributors', [])
    out = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                out.append({'name': item, 'url': ''})
            elif isinstance(item, dict) and item.get('name'):
                out.append({'name': str(item['name']),
                            'url': str(item.get('url') or '')})
    elif isinstance(raw, str) and raw:
        out.append({'name': raw, 'url': ''})
    return out


def scan():
    """扫描 locales/ 返回 {lang: data}，跳过非 json 文件。"""
    langs = {}
    if os.path.isdir(LOCALES):
        for fn in sorted(os.listdir(LOCALES)):
            if fn.endswith('.json'):
                langs[fn[:-5]] = _load(os.path.join(LOCALES, fn))
    return langs


def build_status(langs, only=None):
    """以 REFERENCE 为基准计算各语言进度。"""
    ref = langs.get(REFERENCE[:-5], {}) or {}
    ref_keys = _content_keys(ref)
    rows = []
    for code in sorted(langs):
        if only and code != only:
            continue
        data = langs[code] or {}
        keys = _content_keys(data)
        covered = len(keys & ref_keys)
        if code == SOURCE_LANG:
            status = 'source'
            pct = 1.0
            pct_str = '100%'
        else:
            total = len(ref_keys)
            pct = covered / total if total else 1.0
            pct_str = f'{pct * 100:.1f}%'
            status = 'complete' if keys >= ref_keys else 'partial'
        rows.append({
            'code': code,
            'name': (data or {}).get('__name__', code),
            'covered': covered,
            'total': len(ref_keys),
            'pct': round(pct, 4),
            'pct_str': pct_str,
            'status': status,
            'contributors': _contributors(data),
        })
    return rows


def fmt_contributors(cs):
    if not cs:
        return '-'
    return '; '.join(f"{c['name']}{(' <' + c['url'] + '>') if c['url'] else ''}"
                     for c in cs)


def render_text(rows, ref_total, ref_meta):
    lines = []
    lines.append('FlaskToolkit 翻译状态')
    lines.append('=' * 46)
    lines.append(f'参考语言包: {REFERENCE}（可翻译 key {ref_total}，元信息字段 {ref_meta}）')
    lines.append('')
    lines.append(f'{"语言":<10}{"进度":<10}{"状态":<12}贡献者')
    lines.append('-' * 46)
    for r in rows:
        state = '✔' if r['status'] == 'complete' else ('源语言' if r['status'] == 'source' else '…')
        lines.append(f"{r['name']:<10}{r['pct_str']:<10}{state:<12}{fmt_contributors(r['contributors'])}")
    lines.append('')
    lines.append('提示: 元信息字段以 "__" 为前缀（__name__ 语言名 / __contributors 贡献者），不参与翻译对照。')
    lines.append('      创建新语言包: python tools/i18n_status.py --create <lang> --name "<语言名>"')
    lines.append('      ' + _GITHUB_TIP.replace('\n', '\n      '))
    return '\n'.join(lines)


def cmd_create(lang, name, langs):
    """基于 en.json 模板创建新语言包。内置语言不可创建/修改。"""
    if lang in BUILTIN:
        print(f"错误: {lang} 是内置语言（{REFERENCE} 为参考、{SOURCE_LANG} 为源语言），不可创建/修改",
              file=sys.stderr)
        return 1
    if not _LANG_RE.match(lang):
        print(f"错误: 语言代码 '{lang}' 非法（仅允许字母/数字/连字符，如 fr、fr-FR）", file=sys.stderr)
        return 1
    if lang in langs and langs[lang] is not None:
        print(f"错误: 语言包 {lang}.json 已存在（如需修改请手动编辑 locales/{lang}.json）",
              file=sys.stderr)
        return 1

    ref = langs.get(REFERENCE[:-5], {}) or {}
    new = {}
    for k, v in ref.items():
        if not k.startswith(META_PREFIX):
            new[k] = v  # 复制英文原文作占位，翻译者逐条改为目标语言
    new['__name__'] = name or lang
    new['__contributors'] = []

    path = os.path.join(LOCALES, lang + '.json')
    try:
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(new, f, ensure_ascii=False, indent=2)
            f.write('\n')
    except OSError as e:
        print(f"错误: 创建语言包失败: {e}", file=sys.stderr)
        return 1

    print(f"已创建语言包: locales/{lang}.json（基于 {REFERENCE} 模板，共 {len(new)} 项，请逐条翻译）")
    print(f"请在文件 __contributors 中填写你的贡献信息，然后提交翻译。")
    print('  ' + _GITHUB_TIP.replace('\n', '\n  '))
    return 0


def main():
    ap = argparse.ArgumentParser(description='FlaskToolkit 翻译状态工具')
    ap.add_argument('lang', nargs='?', help='仅查看指定语言包（如 en）')
    ap.add_argument('--json', action='store_true', help='JSON 输出')
    ap.add_argument('--check', action='store_true', help='校验全部语言包 JSON 合法')
    ap.add_argument('--create', metavar='LANG', help='基于 en.json 创建新语言包（内置语言不可创建）')
    ap.add_argument('--name', metavar='NAME', help='创建语言包时的语言名（缺省用语言代码）')
    args = ap.parse_args()

    langs = scan()

    if args.create:
        return cmd_create(args.create, args.name, langs)

    if args.check:
        bad = [c for c, d in langs.items() if d is None]
        if bad:
            print(f'非法 JSON: {", ".join(bad)}', file=sys.stderr)
            return 1
        print('全部语言包 JSON 合法')
        return 0

    rows = build_status(langs, only=args.lang)
    ref = langs.get(REFERENCE[:-5], {}) or {}
    ref_total = len(_content_keys(ref))
    ref_meta = len({k for k in ref if k.startswith(META_PREFIX)})

    if args.json:
        print(json.dumps({
            'reference': REFERENCE,
            'reference_total_keys': ref_total,
            'reference_meta_fields': ref_meta,
            'languages': rows,
        }, ensure_ascii=False, indent=2))
    else:
        print(render_text(rows, ref_total, ref_meta))
    return 0


if __name__ == '__main__':
    sys.exit(main())
