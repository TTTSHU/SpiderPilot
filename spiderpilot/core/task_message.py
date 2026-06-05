"""Generic TaskMessage serialization helpers."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from typing import Any

from spiderpilot.core.models import TaskMessage, TaskSource


def task_message_to_dict(message: TaskMessage) -> dict[str, Any]:
    data = asdict(message)
    if isinstance(message.created_at, datetime):
        data["created_at"] = message.created_at.isoformat()
    return data


def task_message_to_json(message: TaskMessage) -> str:
    return json.dumps(task_message_to_dict(message), ensure_ascii=False)


def task_message_from_dict(data: dict[str, Any]) -> TaskMessage:
    source_data = data.get("source")
    source = TaskSource(**source_data) if isinstance(source_data, dict) else None
    created_at = data.get("created_at")
    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at)
        except ValueError:
            created_at = datetime.now()
    elif not isinstance(created_at, datetime):
        created_at = datetime.now()
    return TaskMessage(
        platform=data["platform"],
        task=data["task"],
        entity_type=data["entity_type"],
        url=data["url"],
        entity_id=data.get("entity_id"),
        source=source,
        context=data.get("context") or {},
        priority=int(data.get("priority", 5)),
        created_at=created_at,
    )


def task_message_from_json(raw: str | bytes) -> TaskMessage:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return task_message_from_dict(json.loads(raw))
