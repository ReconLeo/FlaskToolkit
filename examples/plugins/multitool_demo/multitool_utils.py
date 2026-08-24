# -*- coding: utf-8 -*-
"""
大插件示例的辅助模块（multitool_utils.py）
==========================================
与主插件 `multitool_demo.py` 分离的**辅助 .py 文件**，验证插件包多 .py 分发。
仅提供纯函数文本工具，供主插件 API 与子页面视图函数复用。

注意：辅助模块不含 BasePlugin 子类，扫描器会安全跳过（不会误判为插件）。
"""
import re
from collections import Counter


def analyze_text(text: str) -> dict:
    """文本基础统计：总字符 / 去空白字符 / 单词数 / 句子数"""
    text = text or ""
    words = re.findall(r"[a-zA-Z]+|[\u4e00-\u9fff]+", text)
    sentences = re.findall(r"[。！？!?.]+", text)
    return {
        "char_count": len(text),
        "char_no_space": len(re.sub(r"\s", "", text)),
        "word_count": len(words),
        "sentence_count": len(sentences) or (1 if text.strip() else 0),
    }


def top_words(text: str, n: int = 5) -> list:
    """词频 Top-N：英文按单词、中文按连续汉字切分，返回 [{'word','count'}, ...]"""
    words = re.findall(r"[a-zA-Z]+|[\u4e00-\u9fff]+", (text or "").lower())
    return [{"word": w, "count": c} for w, c in Counter(words).most_common(n)]
