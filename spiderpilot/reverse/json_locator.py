"""Embedded JSON extraction and recursive JSON path search."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class JsonDocument:
    source: str
    data: Any


SCRIPT_JSON_RE = re.compile(
    r"<script[^>]*(?:type=[\"']application/ld\+json[\"']|id=[\"']__NEXT_DATA__[\"'])[^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
NEXT_DATA_RE = re.compile(
    r"<script[^>]*id=[\"']__NEXT_DATA__[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
WINDOW_STATE_PATTERNS = [
    ("window_initial_state", re.compile(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*(?:;|</script>)", re.DOTALL)),
    ("window_preloaded_state", re.compile(r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\})\s*(?:;|</script>)", re.DOTALL)),
]


def extract_embedded_json(html: str) -> list[JsonDocument]:
    docs: list[JsonDocument] = []
    seen = set()

    for match in SCRIPT_JSON_RE.finditer(html):
        raw = _html_unescape(match.group(1).strip())
        data = _parse_json(raw)
        if data is not None:
            key = ("script_json", raw[:200])
            if key not in seen:
                seen.add(key)
                docs.append(JsonDocument(source="embedded_json", data=data))

    for name, pattern in WINDOW_STATE_PATTERNS:
        for match in pattern.finditer(html):
            raw = match.group(1).strip()
            data = _parse_json(raw)
            if data is not None:
                key = (name, raw[:200])
                if key not in seen:
                    seen.add(key)
                    docs.append(JsonDocument(source=name, data=data))
    return docs


def find_json_paths(data: Any, expected: str, path: str = "$", max_hits: int = 20) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    _walk_json(data, expected, path, hits, max_hits)
    return hits


def get_json_path(data: Any, path: str) -> Any:
    if path == "$":
        return data
    tokens = _parse_json_path(path)
    cur = data
    for token in tokens:
        if isinstance(token, int):
            if not isinstance(cur, list) or token >= len(cur):
                return None
            cur = cur[token]
        else:
            if not isinstance(cur, dict) or token not in cur:
                return None
            cur = cur[token]
    return cur


def _walk_json(data: Any, expected: str, path: str, hits: list[dict[str, Any]], max_hits: int) -> None:
    if len(hits) >= max_hits:
        return
    if isinstance(data, dict):
        for key, value in data.items():
            _walk_json(value, expected, f"{path}.{_escape_key(str(key))}", hits, max_hits)
    elif isinstance(data, list):
        for index, value in enumerate(data):
            _walk_json(value, expected, f"{path}[{index}]", hits, max_hits)
    else:
        if str(data) == expected or expected in str(data):
            hits.append({"path": path, "value": data})


def _parse_json_path(path: str) -> list[str | int]:
    if not path.startswith("$"):
        raise ValueError(f"invalid json path: {path}")
    tokens: list[str | int] = []
    i = 1
    while i < len(path):
        if path[i] == ".":
            i += 1
            start = i
            while i < len(path) and path[i] not in ".[":
                i += 1
            tokens.append(path[start:i].replace("\\.", "."))
        elif path[i] == "[":
            end = path.index("]", i)
            tokens.append(int(path[i + 1 : end]))
            i = end + 1
        else:
            raise ValueError(f"invalid json path segment: {path[i:]} in {path}")
    return tokens


def _escape_key(key: str) -> str:
    return key.replace(".", "\\.")


def _parse_json(raw: str) -> Any | None:
    try:
        return json.loads(raw)
    except Exception:
        return None


def _html_unescape(text: str) -> str:
    return text.replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
