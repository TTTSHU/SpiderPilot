"""SpiderPilot Web UI

用户流程：
  1. 创建任务 → 输入平台名 + URL
  2. AI 分析中 → 进度实时展示
  3. 查看结果 → 字段 + 爬虫代码
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import jinja2

from spiderpilot.agent_scanner import scan_agents, write_trigger as write_agent_trigger

app = FastAPI(title="SpiderPilot")

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE = Path("workspace")

_jinja = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(BASE_DIR / "templates")),
    autoescape=True,
)

FRAMEWORK_TEMPLATE = BASE_DIR / "templates" / "framework"


def render(template: str, **ctx) -> HTMLResponse:
    return HTMLResponse(_jinja.get_template(template).render(**ctx))


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ═══════════════════════════════════════════
# 页面路由
# ═══════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """项目列表页"""
    projects = []
    if WORKSPACE.exists():
        for d in sorted(WORKSPACE.iterdir(), reverse=True):
            if not d.is_dir() or d.name.startswith("."):
                continue
            spec_path = d / "spec.yaml"
            spec = {}
            if spec_path.exists():
                try:
                    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
                except Exception:
                    pass

            projects.append({
                "name": d.name,
                "url": spec.get("samples", [{}])[0].get("url", "") if spec.get("samples") else "",
                "status": _task_status(d),
                "fields_count": len(spec.get("fields", {})),
                "updated": _now(),
            })

    return render("index.html", request=request, projects=projects)


@app.get("/task/{task_id}", response_class=HTMLResponse)
async def task_detail(request: Request, task_id: str):
    """任务详情页"""
    task_dir = WORKSPACE / task_id
    if not task_dir.exists():
        return HTMLResponse("任务不存在", status_code=404)

    spec = {}
    spec_path = task_dir / "spec.yaml"
    if spec_path.exists():
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}

    # 读取各阶段状态
    state = {
        "status": _task_status(task_dir),
        "has_probe": (task_dir / "raw.html").exists(),
        "has_analysis": (task_dir / "field_analysis.json").exists(),
        "has_plan": (task_dir / "extraction_plan.yaml").exists(),
        "has_spider": (task_dir / "spider.py").exists(),
        "has_result": (task_dir / "result.json").exists(),
    }

    # 读取分析结果
    analysis = {}
    if state["has_analysis"]:
        try:
            analysis = json.loads((task_dir / "field_analysis.json").read_text(encoding="utf-8"))
        except Exception:
            pass

    # 读取生成的爬虫代码
    spider_code = ""
    if state["has_spider"]:
        spider_code = (task_dir / "spider.py").read_text(encoding="utf-8")

    # 读取日志
    log = ""
    log_path = task_dir / "log.txt"
    if log_path.exists():
        log = log_path.read_text(encoding="utf-8")

    return render(
        "task.html",
        request=request,
        task_id=task_id,
        spec=spec,
        state=state,
        analysis=analysis,
        spider_code=spider_code,
        log=log,
    )


@app.get("/task/{task_id}/raw", response_class=HTMLResponse)
async def raw_html(request: Request, task_id: str):
    """查看原始 HTML"""
    path = WORKSPACE / task_id / "raw.html"
    if not path.exists():
        return HTMLResponse("raw.html 不存在", status_code=404)
    content = path.read_text(encoding="utf-8", errors="replace")
    return HTMLResponse(f"<pre>{content[:50000]}</pre>")


# ═══════════════════════════════════════════
# 操作 API
# ═══════════════════════════════════════════

@app.post("/create", response_class=RedirectResponse)
async def create_task(
    name: str = Form(...),
    url: str = Form(...),
    platform: str = Form(""),
    agent: str = Form(""),
):
    """创建新任务 — 用户输入平台名 + URL"""
    task_id = name.replace(" ", "_").lower()
    task_dir = WORKSPACE / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    spec = {
        "version": 1,
        "name": task_id,
        "platform": platform or task_id,
        "url": url.strip(),
        "agent": agent,
        "created_at": _now(),
        "status": "created",
    }
    (task_dir / "spec.yaml").write_text(
        yaml.safe_dump(spec, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    _log(task_dir, f"任务创建: {url}")

    return RedirectResponse(f"/task/{task_id}", status_code=303)


@app.post("/task/{task_id}/probe")
async def start_probe(task_id: str):
    """触发页面探测（AI Agent 调用）"""
    task_dir = WORKSPACE / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    _update_status(task_dir, "probing")
    _log(task_dir, "开始探测页面...")
    return {"ok": True, "task_id": task_id, "status": "probing"}


@app.post("/task/{task_id}/analysis")
async def save_analysis(task_id: str, body: dict):
    """
    AI Agent 写入分析结果。

    body 格式:
    {
        "page_type": "product_detail",
        "fields": [
            {"name": "title", "value": "样品值", "business_value": 5, "priority": "high", ...}
        ],
        "antibot": {"vendor": null, "status": "clear"},
        "log": "分析完成，找到 15 个字段"
    }
    """
    task_dir = WORKSPACE / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "field_analysis.json").write_text(
        json.dumps(body, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _update_status(task_dir, "analyzed")
    if body.get("log"):
        _log(task_dir, body["log"])
    return {"ok": True}


@app.post("/task/{task_id}/spider")
async def save_spider(task_id: str, body: dict):
    """
    AI Agent 写入生成的爬虫代码。

    body 格式:
    {
        "code": "class EmpikSpider(BaseSpider): ...",
        "plan": {...},  # Extraction Plan
        "log": "生成完成"
    }
    """
    task_dir = WORKSPACE / task_id
    if body.get("code"):
        (task_dir / "spider.py").write_text(body["code"], encoding="utf-8")
    if body.get("plan"):
        (task_dir / "extraction_plan.yaml").write_text(
            yaml.safe_dump(body["plan"], allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
    _update_status(task_dir, "generated")
    if body.get("log"):
        _log(task_dir, body["log"])
    return {"ok": True}


@app.get("/api/agents")
async def list_agents():
    """扫描本地 AI 工具并返回列表"""
    agents = scan_agents()
    if not agents:
        # 如果没有检测到任何 agent，至少返回一个提示
        agents = [{
            "id": "none",
            "name": "未检测到 AI 工具",
            "icon": "❓",
            "description": "请安装 CodeWhale 或其他 AI 工具",
        }]
    return agents


@app.post("/task/{task_id}/trigger")
async def trigger_ai(task_id: str, agent: str = ""):
    """用户选择 AI 工具后触发分析"""
    task_dir = WORKSPACE / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    # 读取 spec 中的 URL
    spec = {}
    spec_path = task_dir / "spec.yaml"
    if spec_path.exists():
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
    url = spec.get("url", "")

    # 如果没有传 agent，尝试从 spec 读取
    if not agent:
        agent = spec.get("agent", "")
    if not agent:
        # 默认用第一个检测到的 agent
        agents = scan_agents()
        agent = agents[0]["id"] if agents else "codewhale"

    # 写入 agent 选择到 spec
    spec["agent"] = agent
    (task_dir / "spec.yaml").write_text(
        yaml.safe_dump(spec, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    _update_status(task_dir, "waiting_ai")

    # 根据 agent 类型写触发文件
    instruction = write_agent_trigger(task_dir, agent, url)
    _log(task_dir, f"触发 {agent}: {instruction}")

    return RedirectResponse(f"/task/{task_id}", status_code=303)


@app.get("/task/{task_id}/think")
async def get_think_stream(task_id: str):
    """返回 AI 思考流"""
    task_dir = WORKSPACE / task_id
    path = task_dir / "think.jsonl"
    if not path.exists():
        return {"lines": []}
    lines = []
    for line in path.read_text(encoding="utf-8").strip().split("\n"):
        if line:
            try:
                lines.append(json.loads(line))
            except Exception:
                pass
    return {"lines": lines}


@app.post("/task/{task_id}/think")
async def append_think(task_id: str, body: dict):
    """AI Agent 写入思考内容"""
    task_dir = WORKSPACE / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    import time
    entry = {
        "time": time.strftime("%H:%M:%S"),
        "text": body.get("text", ""),
    }
    with open(task_dir / "think.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"ok": True}


@app.get("/task/{task_id}/progress")
async def get_progress(task_id: str):
    """返回任务进度（兼容）"""
    task_dir = WORKSPACE / task_id
    progress_path = task_dir / "progress.json"
    if progress_path.exists():
        return json.loads(progress_path.read_text(encoding="utf-8"))
    return {"agents": [], "status": "waiting"}


@app.get("/api/pending")
async def list_pending():
    """列出所有等待 CodeWhale 处理的任务（CodeWhale 调用）"""
    pending = []
    if WORKSPACE.exists():
        for task_dir in sorted(WORKSPACE.iterdir()):
            if not task_dir.is_dir():
                continue
            trigger_path = task_dir / ".trigger"
            if trigger_path.exists():
                try:
                    trigger = json.loads(trigger_path.read_text(encoding="utf-8"))
                except Exception:
                    trigger = {"task_id": task_dir.name}
                spec = {}
                spec_path = task_dir / "spec.yaml"
                if spec_path.exists():
                    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
                pending.append({
                    "task_id": task_dir.name,
                    "url": spec.get("url", ""),
                    "platform": spec.get("platform", ""),
                    "trigger": trigger,
                })
    return pending


@app.post("/task/{task_id}/raw")
async def save_raw_html(task_id: str, body: dict):
    """AI Agent 写入原始 HTML"""
    task_dir = WORKSPACE / task_id
    if body.get("html"):
        (task_dir / "raw.html").write_text(body["html"], encoding="utf-8")
    if body.get("log"):
        _log(task_dir, body["log"])
    return {"ok": True}


# ═══════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════

def _task_status(task_dir: Path) -> str:
    path = task_dir / "status.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return "created"


def _update_status(task_dir: Path, status: str):
    (task_dir / "status.txt").write_text(status, encoding="utf-8")


def _log(task_dir: Path, msg: str):
    line = f"[{_now()}] {msg}\n"
    with open(task_dir / "log.txt", "a", encoding="utf-8") as f:
        f.write(line)


# ═══════════════════════════════════════════
# 启动
# ═══════════════════════════════════════════

def main():
    import uvicorn
    uvicorn.run("spiderpilot.web.app:app", host="0.0.0.0", port=8000, reload=True)
