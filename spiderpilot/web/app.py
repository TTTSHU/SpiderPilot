"""SpiderPilot Web UI — SQLite 存储版"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import jinja2

from spiderpilot.agent_scanner import scan_agents, write_trigger as write_agent_trigger
from spiderpilot.store import (
    create_task, get_task, list_tasks, update_status, update_spec,
    save_analysis, save_spider_code, save_raw_html,
    append_think, get_think_stream,
    append_log, get_log, delete_task,
)

app = FastAPI(title="SpiderPilot")
BASE_DIR = Path(__file__).resolve().parent

_jinja = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(BASE_DIR / "templates")),
    autoescape=True,
)


def render(template: str, **ctx) -> HTMLResponse:
    return HTMLResponse(_jinja.get_template(template).render(**ctx))


# ═══════════════════════════════════════════
# 页面
# ═══════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    tasks = list_tasks()
    projects = []
    for t in tasks:
        projects.append({
            "name": t["id"],
            "url": t.get("url", ""),
            "status": t.get("status", "created"),
            "fields_count": len((t.get("analysis") or {}).get("fields", [])),
            "updated": t.get("updated_at", ""),
        })
    return render("index.html", request=request, projects=projects)


@app.get("/task/{task_id}", response_class=HTMLResponse)
async def task_detail(request: Request, task_id: str):
    task = get_task(task_id)
    if not task:
        return HTMLResponse("任务不存在", status_code=404)

    state = {
        "status": task.get("status", "created"),
        "has_probe": bool(task.get("raw_html")),
        "has_analysis": bool(task.get("analysis", {}).get("fields")),
        "has_spider": bool(task.get("spider_code")),
    }

    spec = task.get("spec", {})
    analysis = task.get("analysis", {})
    spider_code = task.get("spider_code", "")
    log_lines = get_log(task_id)
    think_lines = get_think_stream(task_id)

    return render("task.html", request=request, task_id=task_id,
                  spec=spec, state=state, analysis=analysis,
                  spider_code=spider_code, log="\n".join(log_lines),
                  think_lines=think_lines)


# ═══════════════════════════════════════════
# API
# ═══════════════════════════════════════════

@app.get("/api/agents")
async def api_agents():
    agents = scan_agents()
    if not agents:
        agents = [{"id": "none", "name": "未检测到 AI 工具", "icon": "❓",
                    "description": "请安装 CodeWhale 或其他 AI 工具"}]
    return agents


@app.post("/create", response_class=RedirectResponse)
async def api_create(name: str = Form(...), url: str = Form(...),
                     platform: str = Form(""), agent: str = Form("")):
    task_id = name.replace(" ", "_").lower()
    create_task(task_id, name, url.strip(), platform, agent)
    append_log(task_id, f"任务创建: {url}")
    return RedirectResponse(f"/task/{task_id}", status_code=303)


@app.post("/task/{task_id}/trigger")
async def api_trigger(task_id: str, agent: str = ""):
    task = get_task(task_id) or {}
    spec = task.get("spec", {})
    url = spec.get("url", "")
    if not agent:
        agent = spec.get("agent", "") or scan_agents()[0]["id"] if scan_agents() else "codewhale"

    spec["agent"] = agent
    update_spec(task_id, spec)
    update_status(task_id, "waiting_ai")

    instruction = write_agent_trigger(
        Path("workspace") / task_id, agent, url
    )
    append_log(task_id, f"触发 {agent}: {instruction}")
    return RedirectResponse(f"/task/{task_id}", status_code=303)


@app.post("/task/{task_id}/analysis")
async def api_analysis(task_id: str, body: dict):
    save_analysis(task_id, body)
    return {"ok": True}


@app.post("/task/{task_id}/spider")
async def api_spider(task_id: str, body: dict):
    save_spider_code(task_id, body.get("code", ""), body.get("plan"))
    if body.get("log"):
        append_log(task_id, body["log"])
    return {"ok": True}


@app.post("/task/{task_id}/raw")
async def api_raw(task_id: str, body: dict):
    save_raw_html(task_id, body.get("html", ""))
    if body.get("log"):
        append_log(task_id, body["log"])
    return {"ok": True}


@app.post("/task/{task_id}/think")
async def api_think(task_id: str, body: dict):
    append_think(task_id, body.get("text", ""))
    return {"ok": True}


@app.get("/task/{task_id}/think")
async def api_get_think(task_id: str):
    return {"lines": get_think_stream(task_id)}


@app.post("/task/{task_id}/delete")
async def api_delete(task_id: str):
    delete_task(task_id)
    return RedirectResponse("/", status_code=303)


@app.post("/task/{task_id}/update")
async def api_update(task_id: str, body: dict):
    """更新任务: {"status": "created", "url": "...", "tags": [...]}"""
    task = get_task(task_id) or {}
    spec = task.get("spec", {})
    for key in ("url", "tags", "platform"):
        if key in body:
            spec[key] = body[key]
    if "status" in body:
        update_status(task_id, body["status"])
    update_spec(task_id, spec)
    return {"ok": True}


@app.get("/api/pending")
async def api_pending():
    return [{"task_id": t["id"], "url": t["url"], "platform": t["platform"],
             "agent": t["agent"]}
            for t in list_tasks(status="waiting_ai")]
