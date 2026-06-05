"""Minimal HTML extraction helpers for CSS/XPath MVP."""

from __future__ import annotations

from spiderpilot.reverse.html_selector import TextNodeParser, infer_css_candidates, infer_xpath_candidates


def extract_by_css_selector(html: str, selector: str) -> str | None:
    parser = TextNodeParser()
    parser.feed(html)
    for node in parser.nodes:
        if _node_matches_css(node.tag, node.attrs, selector):
            return node.text or _first_attr_value(node.attrs)
    return None


def extract_by_xpath(html: str, xpath: str) -> str | None:
    parser = TextNodeParser()
    parser.feed(html)
    for node in parser.nodes:
        if _node_matches_xpath(node.tag, node.attrs, node.text, xpath):
            return node.text or _first_attr_value(node.attrs)
    return None


def _node_matches_css(tag: str, attrs: dict[str, str], selector: str) -> bool:
    if selector.startswith("#"):
        return attrs.get("id") == selector[1:].replace("\\#", "#").replace("\\.", ".")
    if "[" in selector and selector.endswith("]"):
        tag_part, rest = selector.split("[", 1)
        if tag_part and tag != tag_part:
            return False
        attr_expr = rest[:-1]
        if "=" not in attr_expr:
            return False
        attr, value = attr_expr.split("=", 1)
        value = value.strip('"').replace('\\"', '"')
        return attrs.get(attr) == value
    if "." in selector:
        parts = selector.split(".")
        tag_part, classes = parts[0], parts[1:]
        if tag_part and tag != tag_part:
            return False
        node_classes = set(attrs.get("class", "").split())
        return all(cls.replace("\\.", ".") in node_classes for cls in classes)
    return tag == selector


def _node_matches_xpath(tag: str, attrs: dict[str, str], text: str, xpath: str) -> bool:
    if xpath.startswith("//*[@id="):
        wanted = _literal_inside(xpath)
        return attrs.get("id") == wanted
    if xpath.startswith("//") and "[@" in xpath:
        tag_part = xpath[2:].split("[@", 1)[0]
        if tag != tag_part:
            return False
        attr_expr = xpath.split("[@", 1)[1].rstrip("]")
        attr, literal = attr_expr.split("=", 1)
        return attrs.get(attr) == _strip_xpath_literal(literal)
    if xpath.startswith("//") and "contains(concat" in xpath:
        tag_part = xpath[2:].split("[", 1)[0]
        if tag != tag_part:
            return False
        wanted = _last_xpath_literal(xpath).strip()
        return wanted in attrs.get("class", "").split()
    if xpath.startswith("//") and "contains(normalize-space(.)," in xpath:
        tag_part = xpath[2:].split("[", 1)[0]
        wanted = _last_xpath_literal(xpath)
        return tag == tag_part and wanted in text
    return False


def _first_attr_value(attrs: dict[str, str]) -> str | None:
    for value in attrs.values():
        if value:
            return value
    return None


def _literal_inside(expr: str) -> str:
    return _strip_xpath_literal(expr.split("=", 1)[1].rstrip("]"))


def _last_xpath_literal(expr: str) -> str:
    # Good enough for MVP generated xpaths.
    if "'" in expr:
        parts = expr.split("'")
        if len(parts) >= 2:
            return parts[-2]
    if '"' in expr:
        parts = expr.split('"')
        if len(parts) >= 2:
            return parts[-2]
    return ""


def _strip_xpath_literal(value: str) -> str:
    value = value.strip()
    if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
        return value[1:-1]
    return value
