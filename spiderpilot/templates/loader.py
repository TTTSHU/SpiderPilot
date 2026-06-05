"""Domain template loading utilities."""

from __future__ import annotations

from importlib.resources import files
from typing import Any

import yaml


TEMPLATE_PACKAGE = "spiderpilot.templates.domains"


def list_templates() -> list[str]:
    """Return available domain template names."""
    root = files(TEMPLATE_PACKAGE)
    return sorted(path.stem for path in root.iterdir() if path.name.endswith(".yaml"))


def load_template(name: str) -> dict[str, Any]:
    """Load a domain template by name."""
    if not name.endswith(".yaml"):
        name = f"{name}.yaml"
    path = files(TEMPLATE_PACKAGE).joinpath(name)
    if not path.is_file():
        available = ", ".join(list_templates())
        raise ValueError(f"Unknown template: {name.removesuffix('.yaml')}. Available: {available}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
