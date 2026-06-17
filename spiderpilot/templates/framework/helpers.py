"""
SpiderPilot Framework — 辅助函数

AI 生成爬虫时可以直接 import 这些函数，无需重复实现。
"""

from __future__ import annotations

import re
from typing import Any


def json_path(data: Any, path: str) -> Any:
    """
    解析 JSONPath 表达式。

    >>> json_path({"a": {"b": [{"c": 1}]}}, "$.a.b[0].c")
    1
    >>> json_path({"a": 1}, "$.a")
    1
    >>> json_path({"a": 1}, "$.b")
    None
    """
    if not path or not isinstance(data, (dict, list)):
        return None
    if path == "$":
        return data

    cur = data
    i = 1
    while i < len(path):
        if path[i] == ".":
            i += 1
            start = i
            while i < len(path) and path[i] not in ".[":
                i += 1
            key = path[start:i].replace("\\.", ".")
            if not isinstance(cur, dict) or key not in cur:
                return None
            cur = cur[key]
        elif path[i] == "[":
            end = path.index("]", i)
            idx = int(path[i + 1:end])
            if not isinstance(cur, list) or idx >= len(cur):
                return None
            cur = cur[idx]
            i = end + 1
        else:
            return None
    return cur


def safe_get(data: dict, *keys: str, default: Any = None) -> Any:
    """
    安全嵌套取字典值。任意层为 None 或不存在时返回 default。

    >>> safe_get({"a": {"b": 1}}, "a", "b")
    1
    >>> safe_get({"a": {"b": 1}}, "a", "x", default="?")
    '?'
    """
    cur = data
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def normalize(value: Any, method: str | None = None) -> Any:
    """
    字段标准化。

    支持的方法:
      strip       — 去首尾空白
      int         — 转整数
      float       — 转浮点
      bool        — 转布尔
      parse_price — "39.99 zł" → 39.99
      parse_count — "1.2k" → 1200, "(123)" → 123
      parse_date  — "2024-01-15" → 保留字符串
    """
    if value is None:
        return None
    if not method:
        return value

    s = str(value).strip()

    if method == "strip":
        return s
    if method == "int":
        try:
            return int(re.sub(r"[^\d\-]", "", s))
        except ValueError:
            return None
    if method == "float":
        try:
            return float(s.replace(",", ".").replace(" ", ""))
        except ValueError:
            return None
    if method == "bool":
        return s.lower() in ("true", "1", "yes", "tak")
    if method == "parse_price":
        m = re.search(r"(\d+(?:[.,]\d+)?)", s.replace(",", "."))
        return float(m.group(1)) if m else None
    if method == "parse_count":
        s = re.sub(r"[()（）]", "", s)
        m = re.match(r"(\d+(?:\.\d+)?)\s*k", s, re.IGNORECASE)
        if m:
            return int(float(m.group(1)) * 1000)
        try:
            return int(re.sub(r"[^\d]", "", s))
        except ValueError:
            return None
    if method == "parse_date":
        return s

    return s


def extract_number(text: str) -> float | None:
    """从文本中提取第一个数字。"""
    m = re.search(r"(\d+(?:[.,]\d+)?)", str(text).replace(",", "."))
    return float(m.group(1)) if m else None


def extract_product_id(url: str) -> str | None:
    """从 Empik/Allegro 类 URL 中提取商品 ID。"""
    for pattern in [
        r",(p\d+)",               # empik
        r"/product/([a-zA-Z0-9\-]+)",  # generic
        r"/(\d{6,})",            # numeric id
        r"/([a-zA-Z0-9]{20,})",  # long alphanumeric
    ]:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


_TABLE = str.maketrans(
    "ąęćłńóśźżĄĆĘŁŃÓŚŹŻ",
    "aecilnoszzACEILNOSZZ"
)


def ascii_fold(text: str) -> str:
    """波兰语等特殊字符转 ASCII。"""
    return text.translate(_TABLE)


def md5(text: str) -> str:
    import hashlib
    return hashlib.md5(text.encode()).hexdigest()
