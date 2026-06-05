from spiderpilot.core.models import TaskMessage, TaskSource
from spiderpilot.core.task_message import task_message_from_json, task_message_to_json
from spiderpilot.queue import MemoryTaskQueue


def test_task_message_json_roundtrip():
    msg = TaskMessage(platform="demo", task="article_detail", entity_type="article", url="https://e.test/a", source=TaskSource(task="listing"))
    raw = task_message_to_json(msg)
    restored = task_message_from_json(raw)
    assert restored.platform == "demo"
    assert restored.source and restored.source.task == "listing"


def test_memory_task_queue():
    q = MemoryTaskQueue()
    q.push(TaskMessage(platform="demo", task="detail", entity_type="item", url="https://e.test/i"))
    msg = q.pop()
    assert msg and msg.task == "detail"
    assert q.pop() is None
