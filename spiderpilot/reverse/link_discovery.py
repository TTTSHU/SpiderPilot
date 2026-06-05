"""Link discovery MVP for list/search/feed pages."""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin


@dataclass
class LinkCandidate:
    url: str
    text: str
    selector: str

    def to_dict(self) -> dict:
        return {"url": self.url, "text": self.text, "selector": self.selector}


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict] = []
        self._current: dict | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            attrs_dict = {k.lower(): v or "" for k, v in attrs}
            if attrs_dict.get("href"):
                self._current = {"href": attrs_dict["href"], "attrs": attrs_dict, "text": []}

    def handle_data(self, data: str) -> None:
        if self._current is not None and data.strip():
            self._current["text"].append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._current is not None:
            self.links.append(self._current)
            self._current = None


def discover_links(html: str, base_url: str, include_patterns: list[str] | None = None, exclude_patterns: list[str] | None = None, limit: int = 100) -> list[LinkCandidate]:
    parser = LinkParser()
    parser.feed(html)
    include_patterns = include_patterns or []
    exclude_patterns = exclude_patterns or []
    candidates: list[LinkCandidate] = []
    seen = set()
    for link in parser.links:
        url = urljoin(base_url, link["href"])
        text = " ".join(link.get("text") or [])
        if include_patterns and not any(pattern in url or pattern in text for pattern in include_patterns):
            continue
        if exclude_patterns and any(pattern in url or pattern in text for pattern in exclude_patterns):
            continue
        if url in seen:
            continue
        seen.add(url)
        candidates.append(LinkCandidate(url=url, text=text, selector=_link_selector(link.get("attrs") or {})))
        if len(candidates) >= limit:
            break
    return candidates


def _link_selector(attrs: dict[str, str]) -> str:
    if attrs.get("id"):
        return f"a#{attrs['id']}"
    if attrs.get("data-testid"):
        return f"a[data-testid=\"{attrs['data-testid']}\"]"
    classes = [c for c in attrs.get("class", "").split() if c]
    if classes:
        return "a." + ".".join(classes[:2])
    return "a[href]"
