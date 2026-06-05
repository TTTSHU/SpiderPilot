"""Heuristic CSS selector inference for HTML values.

This MVP uses Python standard library HTMLParser and intentionally avoids bs4/lxml
runtime dependencies. It produces reviewable selector candidates such as:
- h1
- .product-title
- #price
- span[data-testid="price"]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any


@dataclass
class HtmlNode:
    tag: str
    attrs: dict[str, str]
    text_parts: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(part.strip() for part in self.text_parts if part.strip()).strip()


class TextNodeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[HtmlNode] = []
        self.nodes: list[HtmlNode] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.stack.append(HtmlNode(tag=tag.lower(), attrs={k.lower(): v or "" for k, v in attrs}))

    def handle_data(self, data: str) -> None:
        if self.stack and data.strip():
            self.stack[-1].text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack:
            return
        node = self.stack.pop()
        if node.text or _attrs_contain_value(node.attrs):
            self.nodes.append(node)
        if self.stack and node.text:
            # Propagate text upward so containers can also be candidates, but leaf
            # nodes usually get better scores.
            self.stack[-1].text_parts.append(node.text)


def infer_css_candidates(html: str, expected_value: str, max_candidates: int = 10) -> list[dict[str, Any]]:
    parser = TextNodeParser()
    parser.feed(html)
    candidates = []
    for node in parser.nodes:
        match_location = None
        if expected_value and expected_value in node.text:
            match_location = "text"
        else:
            for attr_name, attr_value in node.attrs.items():
                if expected_value and expected_value in attr_value:
                    match_location = f"attr:{attr_name}"
                    break
        if not match_location:
            continue
        selector = _best_selector(node)
        if not selector:
            continue
        candidates.append(
            {
                "selector": selector,
                "tag": node.tag,
                "match_location": match_location,
                "text": node.text[:300],
                "attrs": node.attrs,
                "score": _selector_score(node, selector, match_location),
            }
        )
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[:max_candidates]


def _best_selector(node: HtmlNode) -> str | None:
    attrs = node.attrs
    if attrs.get("id"):
        return f"#{_css_escape(attrs['id'])}"
    for attr in ["data-testid", "data-test", "data-qa", "itemprop", "name", "aria-label"]:
        if attrs.get(attr):
            return f"{node.tag}[{attr}=\"{_attr_escape(attrs[attr])}\"]"
    classes = [c for c in attrs.get("class", "").split() if c]
    stable_classes = [c for c in classes if not _looks_hashed_class(c)]
    if stable_classes:
        return f"{node.tag}." + ".".join(_css_escape(c) for c in stable_classes[:2])
    if node.tag:
        return node.tag
    return None


def _selector_score(node: HtmlNode, selector: str, match_location: str) -> float:
    score = 0.4
    if selector.startswith("#"):
        score += 0.35
    if "data-testid" in selector or "data-test" in selector or "itemprop" in selector:
        score += 0.3
    if "." in selector:
        score += 0.18
    if match_location == "text":
        score += 0.08
    if node.tag in {"h1", "h2", "h3", "title", "meta", "span", "strong", "a"}:
        score += 0.05
    if len(node.text) > 500:
        score -= 0.2
    return round(min(score, 0.95), 4)


def _looks_hashed_class(value: str) -> bool:
    if len(value) >= 8 and sum(ch.isdigit() for ch in value) >= 3:
        return True
    return value.startswith(("css-", "sc-")) and len(value) > 8


def _css_escape(value: str) -> str:
    return value.replace(" ", "\\ ").replace(".", "\\.").replace("#", "\\#")


def _attr_escape(value: str) -> str:
    return value.replace('"', '\\"')


def _attrs_contain_value(attrs: dict[str, str]) -> bool:
    return any(bool(v) for v in attrs.values())



def infer_xpath_candidates(html: str, expected_value: str, max_candidates: int = 10) -> list[dict[str, Any]]:
    """Infer simple XPath candidates for expected text/attribute values."""
    parser = TextNodeParser()
    parser.feed(html)
    candidates = []
    for node in parser.nodes:
        match_location = None
        if expected_value and expected_value in node.text:
            match_location = "text"
        else:
            for attr_name, attr_value in node.attrs.items():
                if expected_value and expected_value in attr_value:
                    match_location = f"attr:{attr_name}"
                    break
        if not match_location:
            continue
        xpath = _best_xpath(node, expected_value, match_location)
        candidates.append(
            {
                "xpath": xpath,
                "tag": node.tag,
                "match_location": match_location,
                "text": node.text[:300],
                "attrs": node.attrs,
                "score": _selector_score(node, xpath, match_location),
            }
        )
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[:max_candidates]


def _best_xpath(node: HtmlNode, expected_value: str, match_location: str) -> str:
    attrs = node.attrs
    if attrs.get("id"):
        return f"//*[@id={_xpath_literal(attrs['id'])}]"
    for attr in ["data-testid", "data-test", "data-qa", "itemprop", "name", "aria-label"]:
        if attrs.get(attr):
            return f"//{node.tag}[@{attr}={_xpath_literal(attrs[attr])}]"
    classes = [c for c in attrs.get("class", "").split() if c and not _looks_hashed_class(c)]
    if classes:
        cls = classes[0]
        return f"//{node.tag}[contains(concat(' ', normalize-space(@class), ' '), {_xpath_literal(' ' + cls + ' ')})]"
    if match_location.startswith("attr:"):
        attr = match_location.split(":", 1)[1]
        return f"//{node.tag}[contains(@{attr}, {_xpath_literal(expected_value)})]"
    return f"//{node.tag}[contains(normalize-space(.), {_xpath_literal(expected_value)})]"


def _xpath_literal(value: str) -> str:
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = value.split("'")
    return "concat(" + ", \"'\", ".join(f"'{part}'" for part in parts) + ")"
