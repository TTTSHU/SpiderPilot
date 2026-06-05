"""URL pattern inference helpers."""

from __future__ import annotations

from urllib.parse import urlparse


def infer_url_pattern(urls: list[str]) -> str | None:
    if not urls:
        return None
    if len(urls) == 1:
        return urls[0]
    parsed = [urlparse(url) for url in urls]
    if len({(p.scheme, p.netloc) for p in parsed}) != 1:
        return None
    path_parts = [p.path.strip("/").split("/") if p.path.strip("/") else [] for p in parsed]
    if len({len(parts) for parts in path_parts}) != 1:
        return None
    pattern_parts = []
    var_index = 1
    for column in zip(*path_parts):
        values = list(column)
        if len(set(values)) == 1:
            pattern_parts.append(values[0])
        else:
            if all(v.isdigit() for v in values):
                pattern_parts.append(f"{{id{var_index}}}")
            else:
                pattern_parts.append(f"{{var{var_index}}}")
            var_index += 1
    base = f"{parsed[0].scheme}://{parsed[0].netloc}"
    path = "/".join(pattern_parts)
    return base + (f"/{path}" if path else "")
