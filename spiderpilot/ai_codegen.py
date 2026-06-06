"""AI-driven codegen — uses LLM to generate spider code from an Extraction Plan."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from spiderpilot.llm import chat

SYSTEM_CODEGEN = """\
You are a Scrapy spider generator. Given an Extraction Plan with field locations,
you must produce production-ready Scrapy spider code.

Return ONLY the Python code, no markdown fences, no explanations.
Generate:
- A Scrapy Spider class
- start_requests or start_urls
- proper parse method using the extraction paths
- JSONPath via response.json(), CSS via response.css(), XPath via response.xpath()
- Include error handling and fallback
- Include reasonable custom_settings (DOWNLOAD_DELAY, CONCURRENT_REQUESTS, etc.)

Example for JSON response:
```python
import scrapy
import json

class DemoSpider(scrapy.Spider):
    name = "demo"
    start_urls = ["https://example.com/api/products"]
    custom_settings = {"DOWNLOAD_DELAY": 0.5, "CONCURRENT_REQUESTS": 4}

    def parse(self, response):
        data = response.json()
        item = {}
        try:
            item["title"] = self.get_json_path(data, "$.data.title")
            item["price"] = self.get_json_path(data, "$.data.price")
        except Exception as e:
            self.logger.error(f"Parse error: {e}")
        yield item

    def get_json_path(self, data, path):
        ...
```
"""


def ai_generate(plan_path: Path, workspace: Path = Path("workspace"), model: str = "deepseek-v4-flash") -> dict[str, Any]:
    plan = yaml.safe_load(plan_path.read_text(encoding="utf-8")) or {}
    task_name = plan["name"]
    out_dir = workspace / "generated_spiders"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{task_name}_ai.py"

    messages = [
        {"role": "system", "content": SYSTEM_CODEGEN},
        {"role": "user", "content": f"Generate a Scrapy spider for this Extraction Plan:\n\n{yaml.safe_dump(plan, allow_unicode=True, sort_keys=False)}\n\nReturn only Python code."},
    ]
    code = chat(messages, model=model, temperature=0.1, max_tokens=4096)
    code = code.strip()
    if code.startswith("```"):
        lines = code.splitlines()
        lines = [l for l in lines if not l.strip().startswith("```")]
        code = "\n".join(lines)

    out_path.write_text(code, encoding="utf-8")
    return {"task": task_name, "path": str(out_path), "kind": "ai"}
