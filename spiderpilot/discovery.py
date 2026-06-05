"""Discovery runner: extract links and create TaskMessages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from spiderpilot.core.models import TaskMessage, TaskSource
from spiderpilot.core.task_message import task_message_to_dict
from spiderpilot.reverse.link_discovery import discover_links
from spiderpilot.spec import load_spec


def run_discovery(spec_path: Path, workspace: Path = Path("workspace"), target_task: str = "detail", entity_type: str = "item", include: list[str] | None = None) -> dict[str, Any]:
    spec = load_spec(spec_path)
    artifact_root = workspace / "artifacts" / spec.name
    messages = []
    for sample in spec.samples:
        raw_path = artifact_root / sample.id / "raw.html"
        if not raw_path.exists():
            continue
        html = raw_path.read_text(encoding="utf-8", errors="replace")
        for link in discover_links(html, sample.url, include_patterns=include):
            msg = TaskMessage(
                platform=spec.name,
                task=target_task,
                entity_type=entity_type,
                url=link.url,
                source=TaskSource(task=spec.name, entity_type="page", url=sample.url),
                context={"text": link.text, "selector": link.selector},
            )
            messages.append(task_message_to_dict(msg))
    report = {"version": 1, "task": spec.name, "messages_total": len(messages), "messages": messages}
    out_path = artifact_root / "discovered_tasks.yaml"
    out_path.write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return report
