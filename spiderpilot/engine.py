"""CodeWhale 引擎 — Web UI 触发后自动调用 CodeWhale 分析。"""

from __future__ import annotations

import os
import subprocess
import threading

from spiderpilot.store import append_think, update_status, get_task

SERVER = os.environ.get("SPIDER_HOST", "http://127.0.0.1:9002")


def run_ai_analysis(task_id: str):
    """在后台线程调用 CodeWhale CLI 分析。"""
    t = threading.Thread(target=_analyze, args=(task_id,), daemon=True)
    t.start()


def _analyze(task_id: str):
    task = get_task(task_id) or {}
    url = task.get("url") or (task.get("spec") or {}).get("url", "")
    if not url:
        append_think(task_id, "❌ 任务没有 URL")
        return

    update_status(task_id, "probing")

    cli = _detect_cli()
    if not cli:
        append_think(task_id, "❌ 未检测到 CodeWhale")
        append_think(task_id, "安装: brew install codewhale")
        append_think(task_id, "或访问 https://codewhale.ai")
        update_status(task_id, "error")
        return

    append_think(task_id, f"🐋 调用 {cli} 分析...")
    append_think(task_id, f"📡 目标: {url}")

    prompt = f"""你是爬虫分析专家。分析以下任务并写入结果。

任务ID: {task_id}
URL: {url}

步骤:
1. 用 curl_cffi (chrome120) 访问页面获取 HTML
2. 写入思考流: curl -X POST {SERVER}/task/{task_id}/think -H 'Content-Type: application/json' -d '{{"text":"你的思考"}}'
3. 写入原始HTML: curl -X POST {SERVER}/task/{task_id}/raw -H 'Content-Type: application/json' -d '{{"html":"<HTML>","log":"ok"}}'
4. 分析所有字段, 写入: curl -X POST {SERVER}/task/{task_id}/analysis -H 'Content-Type: application/json' -d '{{"page_type":"product_detail","fields":[...],"antibot":{{}},"log":"done"}}'

如果发现 GraphQL 接口, 直接调用 GraphQL 获取更多数据。
每个字段给商业价值评分 1-5。"""

    try:
        result = subprocess.run(
            [cli, "exec", "--auto", prompt],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            append_think(task_id, "✅ CodeWhale 分析完成")
        else:
            append_think(task_id, f"⚠️ CodeWhale 返回错误: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        append_think(task_id, "⚠️ CodeWhale 超时")
    except Exception as e:
        append_think(task_id, f"❌ CodeWhale 异常: {e}")


def _detect_cli() -> str | None:
    for name in ["codewhale", "deepseek"]:
        try:
            subprocess.run([name, "--version"],
                           capture_output=True, timeout=5)
            return name
        except Exception:
            continue
    return None
