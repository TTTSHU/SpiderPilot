"""Smart HTML compression for LLM prompts.

Strategy (in order of priority):
1. JSON responses: send COMPLETE (structured, compact, most likely source)
2. HTML text content: strip tags/scripts/styles, keep only visible text
3. HTML snippets around expected values: context window around each match
4. Truncated raw HTML: fallback
"""

import re
from pathlib import Path


def compress_html_for_llm(html: str, expected_values: list[str] = (), max_chars: int = 12000) -> str:
    """Compress HTML to fit LLM context window while preserving extractable data.

    Priority:
    1. If there are expected values, extract context around each match (most relevant)
    2. Otherwise, strip tags and return visible text (compact)
    3. Fall back to truncated raw HTML
    """
    if not html:
        return ""

    # Strategy 1: Context around expected values
    if expected_values:
        parts = []
        html_lower = html.lower()
        for value in expected_values:
            idx = html_lower.find(value.lower())
            if idx >= 0:
                start = max(0, idx - 500)
                end = min(len(html), idx + len(value) + 500)
                snippet = html[start:end]
                # Strip scripts/styles from snippet
                snippet = re.sub(r'<script[^>]*>.*?</script>', '', snippet, flags=re.DOTALL | re.IGNORECASE)
                snippet = re.sub(r'<style[^>]*>.*?</style>', '', snippet, flags=re.DOTALL | re.IGNORECASE)
                # Strip tags but keep content
                snippet = re.sub(r'<[^>]+>', ' ', snippet)
                snippet = re.sub(r'\s+', ' ', snippet).strip()
                if snippet and snippet not in parts:
                    parts.append(f'[Context around "{value}"]:\n{snippet}')

        if parts:
            result = "\n\n".join(parts)
            if len(result) <= max_chars:
                return result

    # Strategy 2: Strip tags, keep text content
    clean = html
    # Remove scripts, styles, comments
    clean = re.sub(r'<script[^>]*>.*?</script>', '', clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<!--.*?-->', '', clean, flags=re.DOTALL)
    # Convert block elements to newlines
    clean = re.sub(r'</?(div|p|h[1-6]|li|tr|br|section|article|header|footer|nav)[^>]*>', '\n', clean, flags=re.IGNORECASE)
    # Strip all remaining tags
    clean = re.sub(r'<[^>]+>', ' ', clean)
    # Collapse whitespace
    clean = re.sub(r'\n\s*\n', '\n', clean)
    clean = re.sub(r'[ \t]+', ' ', clean)
    clean = '\n'.join(line.strip() for line in clean.splitlines() if line.strip())

    if len(clean) <= max_chars:
        return clean

    # Strategy 3: Truncated clean text
    return clean[:max_chars] + "\n...[truncated]"


def collect_artifacts_smart(artifact_root: Path, samples, expected_values: dict[str, list[str]] = None) -> str:
    """Collect probe artifacts optimized for LLM context.

    Priority:
    1. ALL JSON responses (complete, no truncation) - these are compact and most valuable
    2. Compressed HTML text content
    3. Full HTML only as last resort
    """
    parts = []
    expected_values = expected_values or {}
    all_expected = []
    for vals in expected_values.values():
        all_expected.extend(vals)

    for sample in samples:
        sample_dir = artifact_root / sample.id
        parts.append(f"\n=== Sample: {sample.id} ({sample.url}) ===")

        # 1. JSON responses: FULL, no truncation (they're compact)
        for response_dir in [sample_dir / "responses", sample_dir / "cloak" / "responses"]:
            if not response_dir.exists():
                continue
            for json_file in sorted(response_dir.glob("*.json")):
                text = _read_text(json_file)
                if text and text.strip().startswith("{"):
                    # Keep JSON responses full - they're the most valuable data
                    parts.append(f"--- JSON: {json_file.relative_to(sample_dir)} (FULL) ---\n{text}")

        # 2. HTML: compressed, text-only
        raw_html = _read_text(sample_dir / "raw.html")
        rendered_html = _read_text(sample_dir / "cloak" / "rendered.html")

        html_to_use = rendered_html or raw_html
        if html_to_use:
            compressed = compress_html_for_llm(html_to_use, all_expected, max_chars=8000)
            source = "rendered.html" if rendered_html else "raw.html"
            parts.append(f"--- HTML: {source} (compressed) ---\n{compressed}")

    return "\n".join(parts)


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")
