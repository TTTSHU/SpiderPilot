"""AI agent scanner — detects local AI tools and maps to trigger instructions."""

from __future__ import annotations

import os
from pathlib import Path


AGENT_DEFINITIONS = {
    "codewhale": {
        "name": "CodeWhale",
        "icon": "🐋",
        "checks": [
            lambda home: (home / ".codewhale").is_dir(),
            lambda home: (home / ".deepseek").is_dir(),
        ],
        "trigger_type": "file",
        "description": "写入 .trigger 文件，在 CodeWhale 中说「处理 spiderpilot 待办」",
    },
    "claude": {
        "name": "Claude Code",
        "icon": "🧠",
        "checks": [
            lambda home: (home / ".claude").is_dir(),
        ],
        "trigger_type": "file",
        "description": "写入 prompt.md，在 Claude 中说「读取并执行 prompt.md」",
    },
    "cursor": {
        "name": "Cursor",
        "icon": "🖱️",
        "checks": [
            lambda home: (home / ".cursor").is_dir(),
        ],
        "trigger_type": "file",
        "description": "写入 prompt.md，在 Cursor chat 中说「读取并执行 prompt.md」",
    },
    "codex": {
        "name": "Codex (OpenAI)",
        "icon": "🤖",
        "checks": [
            lambda home: (home / ".codex").is_dir(),
        ],
        "trigger_type": "file",
        "description": "写入 prompt.md，在 Codex 中说「执行 prompt.md」",
    },
    "windsurf": {
        "name": "Windsurf",
        "icon": "🌊",
        "checks": [
            lambda home: (home / ".windsurf").is_dir(),
            lambda home: (home / ".codeium").is_dir(),
        ],
        "trigger_type": "file",
        "description": "写入 prompt.md，在 Windsurf Cascade 中执行",
    },
    "kiro": {
        "name": "Kiro",
        "icon": "🦊",
        "checks": [
            lambda home: (home / ".kiro").is_dir(),
        ],
        "trigger_type": "file",
        "description": "写入 prompt.md，在 Kiro 中执行",
    },
    "gemini": {
        "name": "Gemini CLI",
        "icon": "💎",
        "checks": [
            lambda home: bool(os.popen("which gemini 2>/dev/null").read().strip()),
        ],
        "trigger_type": "file",
        "description": "写入 prompt.md，运行 `gemini spiderpilot_task.md`",
    },
}


def scan_agents(home_dir: str | Path | None = None) -> list[dict]:
    """
    扫描本地 AI 工具。

    Returns:
        [{"id": "codewhale", "name": "CodeWhale", "icon": "🐋", "description": "..."}, ...]
    """
    home = Path(home_dir or os.path.expanduser("~"))
    found = []

    for agent_id, cfg in AGENT_DEFINITIONS.items():
        detected = False
        for check in cfg["checks"]:
            try:
                if check(home):
                    detected = True
                    break
            except Exception:
                pass

        if detected:
            found.append({
                "id": agent_id,
                "name": cfg["name"],
                "icon": cfg["icon"],
                "trigger_type": cfg["trigger_type"],
                "description": cfg["description"],
            })

    return found


def get_agent_instructions(agent_id: str, task_id: str, url: str) -> str:
    """
    生成针对特定 AI 工具的操作指令。

    Returns:
        用户需要执行的自然语言指令
    """
    cfg = AGENT_DEFINITIONS.get(agent_id, {})
    name = cfg.get("name", "AI 助手")

    if agent_id == "codewhale":
        return f"处理 spiderpilot 待办任务 {task_id}"
    else:
        return (
            f"请读取 workspace/{task_id}/prompt.md 文件，"
            f"按照里面的要求分析页面 {url}，"
            f"将结果写入 workspace/{task_id}/field_analysis.json"
        )


def write_trigger(task_dir: Path, agent_id: str, url: str) -> str:
    """
    根据 agent 类型写入对应的触发文件。

    Returns:
        给用户看的提示文字
    """
    import json

    task_id = task_dir.name
    agent_cfg = AGENT_DEFINITIONS.get(agent_id, {})
    agent_name = agent_cfg.get("name", agent_id)

    # 通用：写 trigger 文件
    trigger = {
        "task_id": task_id,
        "url": url,
        "agent": agent_id,
        "action": "analyze",
    }
    (task_dir / ".trigger").write_text(
        json.dumps(trigger, ensure_ascii=False), encoding="utf-8"
    )

    # 写通用 prompt.md（非 CodeWhale 的 agent 需要）
    if agent_id != "codewhale":
        prompt = f"""# SpiderPilot Task: {task_id}

## 任务目标
分析以下 URL 的页面结构和数据字段，生成爬虫代码。

URL: {url}

## 操作步骤

1. 爬取页面 {url}，获取原始 HTML 和 API 响应
2. 将原始 HTML 写入 workspace/{task_id}/raw.html
3. 分析页面中所有有价值的字段（标题、价格、描述、店铺等）
4. 将分析结果写入 workspace/{task_id}/field_analysis.json，格式：

```json
{{
  "page_type": "product_detail",
  "fields": [
    {{
      "name": "title",
      "value": "实际值",
      "type": "str",
      "source": "json_response 或 html",
      "path": "$.data.title 或 .product-title",
      "business_value": 5,
      "priority": "high"
    }}
  ],
  "antibot": {{"status": "clear", "vendor": null}}
}}
```

5. 写入完成后，Web UI 会自动刷新显示结果。
"""
        (task_dir / "prompt.md").write_text(prompt, encoding="utf-8")

    if agent_id == "codewhale":
        return "在 CodeWhale 中说「处理 spiderpilot 待办」"
    elif agent_id == "claude":
        return "在 Claude Code 中说「读取并执行 workspace/{}/prompt.md」".format(task_id)
    elif agent_id == "cursor":
        return "在 Cursor Chat 中打开 workspace/{}/prompt.md 并执行".format(task_id)
    elif agent_id == "codex":
        return "在 Codex 中执行 workspace/{}/prompt.md".format(task_id)
    elif agent_id == "windsurf":
        return "在 Windsurf Cascade 中执行 workspace/{}/prompt.md".format(task_id)
    elif agent_id == "kiro":
        return "在 Kiro 中执行 workspace/{}/prompt.md".format(task_id)
    elif agent_id == "gemini":
        return "运行: gemini workspace/{}/prompt.md".format(task_id)
    else:
        return "执行 workspace/{}/prompt.md".format(task_id)
