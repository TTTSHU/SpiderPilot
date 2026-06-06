"""SpiderPilot web UI with FastAPI."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from spiderpilot.ai_codegen import ai_generate
from spiderpilot.ai_repair import ai_repair_plan
from spiderpilot.ai_reverse import ai_reverse
from spiderpilot.probe.http_probe import run_http_probe
from spiderpilot.runner.local_runner import run_plan
from spiderpilot.spec import load_spec
from spiderpilot.validator.result_validator import validate_results

app = FastAPI(title="SpiderPilot")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

WORKSPACE = Path("workspace")


def _task_dir(name: str) -> Path:
    return WORKSPACE / "specs"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    tasks = []
    specs_dir = WORKSPACE / "specs"
    if specs_dir.exists():
        for f in sorted(specs_dir.glob("*.yaml"), reverse=True):
            try:
                spec = yaml.safe_load(f.read_text(encoding="utf-8"))
                tasks.append({
                    "name": spec.get("name", f.stem),
                    "samples": len(spec.get("samples", [])),
                    "fields": list(spec.get("fields", {}).keys()),
                    "path": str(f),
                })
            except Exception:
                tasks.append({"name": f.stem, "samples": 0, "fields": [], "path": str(f)})
    return templates.TemplateResponse("index.html", {"request": request, "tasks": tasks})


@app.post("/create", response_class=RedirectResponse)
async def create_task(
    name: str = Form(...),
    urls: str = Form(...),
    fields_data: str = Form("[]"),
    template: str = Form("generic"),
):
    url_list = [u.strip() for u in urls.strip().splitlines() if u.strip()]
    if not url_list:
        return RedirectResponse("/", status_code=303)
    fields = json.loads(fields_data) if fields_data else []
    samples = []
    for i, line in enumerate(urllist := url_list):
        parts = line.split("|")
        url = parts[0].strip()
        sample_id = f"s{i+1}"
        expected = {}
        for pair in parts[1:]:
            if "=" in pair:
                k, v = pair.split("=", 1)
                expected[k.strip()] = {"equals": v.strip()}
        samples.append({"id": sample_id, "url": url, "expected": expected})
    field_defs = {}
    for f in fields:
        field_defs[f["name"]] = {"type": f.get("type", "string"), "required": f.get("required", True)}
    if not field_defs:
        all_keys = set()
        for s in samples:
            all_keys.update(s["expected"].keys())
        for k in sorted(all_keys):
            field_defs[k] = {"type": "string", "required": True}

    spec = {"version": 1, "name": name, "target_type": "detail", "samples": samples, "fields": field_defs}
    specs_dir = _task_dir(name)
    specs_dir.mkdir(parents=True, exist_ok=True)
    path = specs_dir / f"{name}.yaml"
    path.write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return RedirectResponse(f"/task/{name}", status_code=303)


@app.get("/task/{name}", response_class=HTMLResponse)
async def task_detail(request: Request, name: str):
    spec_path = WORKSPACE / "specs" / f"{name}.yaml"
    if not spec_path.exists():
        return HTMLResponse("Task not found", status_code=404)
    spec = load_spec(spec_path)

    # Collect run state
    state = {}
    artifact_root = WORKSPACE / "artifacts" / name
    plan_path = WORKSPACE / "plans" / f"{name}.yaml"
    result_path = WORKSPACE / "results" / f"{name}.json"
    validation_path = WORKSPACE / "results" / f"{name}_validation.yaml"
    gen_dir = WORKSPACE / "generated_spiders"
    gen_files = sorted(gen_dir.glob(f"{name}*")) if gen_dir.exists() else []

    state["has_probe"] = (artifact_root / "probe_report.yaml").exists()
    state["has_plan"] = plan_path.exists()
    state["has_result"] = result_path.exists()
    state["has_validation"] = validation_path.exists()
    state["has_codegen"] = bool(gen_files)

    if state["has_plan"]:
        plan = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
        state["plan_source"] = plan.get("source", {}).get("type")
        state["plan_fields"] = plan.get("fields", {})
    if state["has_validation"]:
        val = yaml.safe_load(validation_path.read_text(encoding="utf-8"))
        state["validation_ok"] = val.get("ok")
        state["hit_rate"] = val.get("field_hit_rate")
    if state["has_result"]:
        result = json.loads(result_path.read_text(encoding="utf-8"))
        state["result_preview"] = json.dumps(result[:3], ensure_ascii=False, indent=2)

    return templates.TemplateResponse("task.html", {
        "request": request,
        "spec": spec,
        "name": name,
        "state": state,
        "spec_path": str(spec_path),
        "plan_path": str(plan_path),
        "result_path": str(result_path),
        "validation_path": str(validation_path),
    })


@app.post("/task/{name}/probe", response_class=RedirectResponse)
async def task_probe(name: str):
    spec_path = WORKSPACE / "specs" / f"{name}.yaml"
    run_http_probe(spec_path, workspace=WORKSPACE)
    return RedirectResponse(f"/task/{name}", status_code=303)


@app.post("/task/{name}/reverse-ai", response_class=RedirectResponse)
async def task_reverse_ai(name: str):
    spec_path = WORKSPACE / "specs" / f"{name}.yaml"
    ai_reverse(spec_path, workspace=WORKSPACE)
    return RedirectResponse(f"/task/{name}", status_code=303)


@app.post("/task/{name}/generate-ai", response_class=RedirectResponse)
async def task_generate_ai(name: str):
    plan_path = WORKSPACE / "plans" / f"{name}.yaml"
    ai_generate(plan_path, workspace=WORKSPACE)
    return RedirectResponse(f"/task/{name}", status_code=303)


@app.post("/task/{name}/run", response_class=RedirectResponse)
async def task_run(name: str):
    spec_path = WORKSPACE / "specs" / f"{name}.yaml"
    plan_path = WORKSPACE / "plans" / f"{name}.yaml"
    run_plan(spec_path, plan_path, workspace=WORKSPACE)
    return RedirectResponse(f"/task/{name}", status_code=303)


@app.post("/task/{name}/validate", response_class=RedirectResponse)
async def task_validate(name: str):
    spec_path = WORKSPACE / "specs" / f"{name}.yaml"
    result_path = WORKSPACE / "results" / f"{name}.json"
    validate_results(spec_path, result_path, workspace=WORKSPACE)
    return RedirectResponse(f"/task/{name}", status_code=303)


@app.post("/task/{name}/repair-ai", response_class=RedirectResponse)
async def task_repair_ai(name: str):
    plan_path = WORKSPACE / "plans" / f"{name}.yaml"
    validation_path = WORKSPACE / "results" / f"{name}_validation.yaml"
    ai_repair_plan(plan_path, validation_path, workspace=WORKSPACE)
    return RedirectResponse(f"/task/{name}", status_code=303)


@app.post("/task/{name}/delete", response_class=RedirectResponse)
async def task_delete(name: str):
    import shutil
    for d in [
        WORKSPACE / "specs" / f"{name}.yaml",
        WORKSPACE / "artifacts" / name,
        WORKSPACE / "plans" / f"{name}.yaml",
        WORKSPACE / "results" / f"{name}.json",
        WORKSPACE / "results" / f"{name}_validation.yaml",
        WORKSPACE / "results" / f"{name}_repair.yaml",
        WORKSPACE / "signatures" / name,
    ]:
        if d.is_file():
            d.unlink(missing_ok=True)
        elif d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
    return RedirectResponse("/", status_code=303)
