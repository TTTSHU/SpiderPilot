"""Queue abstractions for SpiderPilot TaskMessage.

Redis is optional. The module exposes a small interface and a memory queue for
tests; Redis List support is used when redis-py is installed.
"""

from __future__ import annotations

from collections import deque
from typing import Protocol

from spiderpilot.core.models import TaskMessage
from spiderpilot.core.task_message import task_message_from_json, task_message_to_json


class TaskQueue(Protocol):
    def push(self, message: TaskMessage) -> None: ...
    def pop(self) -> TaskMessage | None: ...


class MemoryTaskQueue:
    def __init__(self) -> None:
        self._items: deque[str] = deque()

    def push(self, message: TaskMessage) -> None:
        self._items.append(task_message_to_json(message))

    def pop(self) -> TaskMessage | None:
        if not self._items:
            return None
        return task_message_from_json(self._items.popleft())


class RedisListTaskQueue:
    def __init__(self, redis_client, key: str) -> None:
        self.redis = redis_client
        self.key = key

    def push(self, message: TaskMessage) -> None:
        self.redis.lpush(self.key, task_message_to_json(message))

    def pop(self) -> TaskMessage | None:
        raw = self.redis.rpop(self.key)
        if raw is None:
            return None
        return task_message_from_json(raw)
