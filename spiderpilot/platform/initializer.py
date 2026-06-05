"""Platform workspace initialization."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from spiderpilot.templates.loader import load_template


PLATFORM_SUBDIRS = ["specs", "plans", "artifacts", "generated_spiders", "results"]


def init_platform(
    name: str,
    domain: str | None = None,
    template: str = "generic",
    workspace: Path = Path("workspace/platforms"),
) -> Path:
    """Create a platform workspace from a domain template."""
    template_data = load_template(template)
    platform_dir = workspace / name
    platform_dir.mkdir(parents=True, exist_ok=True)

    for subdir in PLATFORM_SUBDIRS:
        (platform_dir / subdir).mkdir(parents=True, exist_ok=True)

    platform_config: dict[str, Any] = {
        "version": 1,
        "name": name,
        "domain": domain,
        "template": template_data.get("name", template),
        "description": None,
    }
    spider_plan: dict[str, Any] = {
        "version": 1,
        "platform": name,
        "domain": domain,
        "template": template_data.get("name", template),
        "entities": template_data.get("entities", {}),
        "spiders": template_data.get("spiders", {}),
        "crawl_graph": template_data.get("crawl_graph", {"nodes": [], "edges": []}),
    }

    _write_yaml_if_missing(platform_dir / "platform.yaml", platform_config)
    _write_yaml_if_missing(platform_dir / "spider_plan.yaml", spider_plan)
    return platform_dir


def _write_yaml_if_missing(path: Path, data: dict[str, Any]) -> None:
    if path.exists():
        return
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
