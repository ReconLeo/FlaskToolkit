# -*- coding: utf-8 -*-
"""扫描框架模板中缺失的中文 key（i18n 完整性检查补充）

与 tools/i18n_status.py（语言包侧，以 en.json 为基准查各语言进度）互补：
本工具扫描 templates/ 下调用 t()/window.T()/T() 的中文文案，若未收录到
locales/en.json（key 即中文原文），列出缺失项及其来源文件。

用法：python tools/scan_missing_i18n.py
"""
import re
import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_en = json.load(open(os.path.join(_ROOT, 'locales', 'en.json'), encoding='utf-8'))
_tpl_re = re.compile(r"(?:\bt\(|window\.T\(|(?<![.\w])T\()\s*['\"]([^'\"]+)['\"]\s*(?:,|\))")
_cjk = re.compile(r'[\u4e00-\u9fff]')

missing = {}
for dp, ds, fns in os.walk(os.path.join(_ROOT, 'templates')):
    if 'plugins' in dp.split(os.sep) or 'frontend_tools' in dp.split(os.sep):
        continue
    for fn in fns:
        if not fn.endswith('.html'):
            continue
        text = open(os.path.join(dp, fn), encoding='utf-8').read()
        for m in _tpl_re.finditer(text):
            k = m.group(1)
            if _cjk.search(k) and k not in _en:
                missing.setdefault(k, []).append(os.path.join(dp, fn))

print(f"缺失中文 key 数: {len(missing)}\n")
for k, files in sorted(missing.items()):
    print(f"{k}\t<-\t{files[0]}")
