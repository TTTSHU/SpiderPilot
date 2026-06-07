"""SpiderPilot web UI with FastAPI."""

import json
import traceback
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import jinja2

from spiderpilot.ai_codegen import ai_generate
from spiderpilot.ai_repair import ai_repair_plan
from spiderpilot.ai_reverse import ai_reverse
from spiderpilot.probe.http_probe import run_http_probe
from spiderpilot.runner.local_runner import run_plan
from spiderpilot.spec import load_spec
from spiderpilot.validator.result_validator import validate_results

app = FastAPI(title="SpiderPilot")
BASE_DIR = Path(__file__).resolve().parent
WORKSPACE = Path("workspace")

_jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(BASE_DIR / "templates")))

def render(template_file: str, **ctx) -> HTMLResponse:
    return HTMLResponse(content=_jinja_env.get_template(template_file).render(**ctx))

def safe_action(label: str, fn, *args, **kwargs) -> str | None:
    """Call fn, return error string or None on success."""
    try:
        fn(*args, **kwargs)
    except Exception:
        return f"{label} failed:\n{traceback.format_exc()}"
    return None

def task_spec_path(task_id: str) -> Path:
    return WORKSPACE / "specs" / f"{task_id}.yaml"

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    tasks = []
    specs_dir = WORKSPACE / "specs"
    if specs_dir.exists():
        for f in sorted(specs_dir.glob("*.yaml"), reverse=True):
            try:
                spec = yaml.safe_load(f.read_text(encoding="utf-8"))
                tasks.append({
                    "task_id": spec.get("name", f.stem),
                    "samples": len(spec.get("samples", [])),
                    "fields": list(spec.get("fields", {}).keys()),
                })
            except Exception:
                tasks.append({"task_id": f.stem, "samples": 0, "fields": []})
    return render("index.html", request=request, tasks=tasks)

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
    for i, line in enumerate(url_list):
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
        all_keys: set = set()
        for s in samples:
            all_keys.update(s["expected"].keys())
        for k in sorted(all_keys):
            field_defs[k] = {"type": "string", "required": True}
    spec = {"version": 1, "name": name, "target_type": "detail", "samples": samples, "fields": field_defs}
    task_spec_path(name).parent.mkdir(parents=True, exist_ok=True)
    task_spec_path(name).write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return RedirectResponse(f"/task/{name}", status_code=303)

@app.get("/task/{task_id}", response_class=HTMLResponse)
async def task_detail(request: Request, task_id: str):
    spec_path = task_spec_path(task_id)
    if not spec_path.exists():
        return HTMLResponse("Task not found", status_code=404)
    spec = load_spec(spec_path)
    state: dict[str, Any] = {
        "has_probe": (WORKSPACE / "artifacts" / task_id / "probe_report.yaml").exists(),
        "has_plan": (WORKSPACE / "plans" / f"{task_id}.yaml").exists(),
        "has_result": (WORKSPACE / "results" / f"{task_id}.json").exists(),
        "has_validation": (WORKSPACE / "results" / f"{task_id}_validation.yaml").exists(),
    }
    if state["has_plan"]:
        plan = yaml.safe_load((WORKSPACE / "plans" / f"{task_id}.yaml").read_text(encoding="utf-8"))
        state["plan_source"] = plan.get("source", {}).get("type", "?")
        state["plan_fields"] = plan.get("fields", {})
    if state["has_validation"]:
        val = yaml.safe_load((WORKSPACE / "results" / f"{task_id}_validation.yaml").read_text(encoding="utf-8"))
        state["validation_ok"] = val.get("ok")
        state["hit_rate"] = val.get("field_hit_rate", 0)
    if state["has_result"]:
        result = json.loads((WORKSPACE / "results" / f"{task_id}.json").read_text(encoding="utf-8"))
        state["result_preview"] = json.dumps(result[:3], ensure_ascii=False, indent=2)
    warn_path = WORKSPACE / "artifacts" / task_id / "probe_warnings.txt"
    state["probe_warnings"] = warn_path.read_text(encoding="utf-8") if warn_path.exists() else None
    return render("task.html", request=request, task_id=task_id, spec=spec, state=state, error=request.query_params.get("error"))

    warn_path = WORKSPACE / "artifacts" / task_id / "probe_warnings.txt"
def redirect_with_error(task_id: str, msg: str) -> RedirectResponse:
    return RedirectResponse(f"/task/{task_id}?error={msg}", status_code=303)

@app.post("/task/{task_id}/probe", response_class=RedirectResponse)
async def task_probe(task_id: str):
    """Smart probe: run in background thread to avoid event loop conflicts."""
    import concurrent.futures
    from spiderpilot.probe.smart_probe import smart_probe
    spec_path = task_spec_path(task_id)

    def run():
        report = smart_probe(spec_path, WORKSPACE, wait_seconds=8)
        sample = report["samples"][0] if report.get("samples") else {}
        warn_path = WORKSPACE / "artifacts" / task_id / "probe_warnings.txt"
        if sample.get("probe_method") == "cloakbrowser":
            warn_path.write_text(
                "Method: CloakBrowser (curl_cffi blocked)
"
                "API responses: " + str(sample.get("curl_success", 0)) + "
"
                "Tip: Run AI Analysis to extract fields from captured data.
",
                encoding="utf-8"
            )
        else:
            warn_path.write_text(
                "Method: curl_cffi (TLS impersonation)
"
                "API responses: " + str(sample.get("curl_success", 0)) + "
",
                encoding="utf-8"
            )
        return report

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(run)
        future.result(timeout=120)
    except Exception as e:
        import traceback
        return redirect_with_error(task_id, "Probe failed:
" + str(traceback.format_exc())[:1000])
    finally:
        pool.shutdown(wait=False)
    return RedirectResponse("/task/" + task_id, status_code=303)


@app.post("/task/{task_id}/cloak-probe", response_class=RedirectResponse)
@app.post("/task/{task_id}/cloak-probe", response_class=RedirectResponse)
@app.post("/task/{task_id}/cloak-probe", response_class=RedirectResponse)
async def task_cloak_probe(task_id: str):
    from spiderpilot.probe.cloak_cdp import capture_with_cloakbrowser
    spec = load_spec(task_spec_path(task_id))
    for sample in spec.samples:
        sample_dir = WORKSPACE / "artifacts" / task_id / sample.id / "cloak"
        try:
            capture_with_cloakbrowser(sample.url, sample_dir, wait_seconds=15)
        except Exception as e:
            import traceback
            return redirect_with_error(task_id, "CloakBrowser failed: " + str(traceback.format_exc())[:500])
    return RedirectResponse("/task/" + task_id, status_code=303)

@app.post("/task/{task_id}/generate-ai", response_class=RedirectResponse)
async def task_generate_ai(task_id: str):
    plan_path = WORKSPACE / "plans" / f"{task_id}.yaml"
    err = safe_action("generate-ai", ai_generate, plan_path, WORKSPACE)
    if err:
        return redirect_with_error(task_id, err)
    return RedirectResponse(f"/task/{task_id}", status_code=303)

@app.post("/task/{task_id}/run", response_class=RedirectResponse)
async def task_run(task_id: str):
    spec_path = task_spec_path(task_id)
    plan_path = WORKSPACE / "plans" / f"{task_id}.yaml"
    err = safe_action("run", run_plan, spec_path, plan_path, WORKSPACE)
    if err:
        return redirect_with_error(task_id, err)
    return RedirectResponse(f"/task/{task_id}", status_code=303)

@app.post("/task/{task_id}/validate", response_class=RedirectResponse)
async def task_validate(task_id: str):
    spec_path = task_spec_path(task_id)
    result_path = WORKSPACE / "results" / f"{task_id}.json"
    err = safe_action("validate", validate_results, spec_path, result_path, WORKSPACE)
    if err:
        return redirect_with_error(task_id, err)
    return RedirectResponse(f"/task/{task_id}", status_code=303)

@app.post("/task/{task_id}/repair-ai", response_class=RedirectResponse)
async def task_repair_ai(task_id: str):
    plan_path = WORKSPACE / "plans" / f"{task_id}.yaml"
    validation_path = WORKSPACE / "results" / f"{task_id}_validation.yaml"
    err = safe_action("repair-ai", ai_repair_plan, plan_path, validation_path, WORKSPACE)
    if err:
        return redirect_with_error(task_id, err)
    return RedirectResponse(f"/task/{task_id}", status_code=303)


@app.get("/task/{task_id}/progress")
async def task_progress(task_id: str):
    """Return current probe progress."""
    import json
    progress_path = WORKSPACE / "artifacts" / task_id / "probe_progress.txt"
    result_paths = []
    for sample_dir in sorted((WORKSPACE / "artifacts" / task_id).glob("s*")):
        pp = sample_dir / "probe_progress.txt"
        if pp.exists():
            result_paths.append(pp.read_text(encoding="utf-8"))
    if result_paths:
        return {"progress": "\n".join(result_paths)}
    if progress_path.exists():
        return {"progress": progress_path.read_text(encoding="utf-8")}
    return {"progress": ""}

@app.post("/task/{task_id}/delete", response_class=RedirectResponse)
async def task_delete(task_id: str):
    import shutil
    for p in [
        task_spec_path(task_id),
        WORKSPACE / "artifacts" / task_id,
        WORKSPACE / "plans" / f"{task_id}.yaml",
        WORKSPACE / "results" / f"{task_id}.json",
        WORKSPACE / "results" / f"{task_id}_validation.yaml",
        WORKSPACE / "signatures" / task_id,
    ]:
        if p.is_file():
            p.unlink(missing_ok=True)
        elif p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
    return RedirectResponse("/", status_code=303)

# ============================================================
# Settings page
# ============================================================

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    from spiderpilot.config_store import load_config
    cfg = load_config()
    return render("settings.html", request=request, cfg=cfg)

@app.post("/settings", response_class=RedirectResponse)
async def settings_save(
    api_key: str = Form(""),
    api_base: str = Form("https://api.deepseek.com/v1"),
    model: str = Form("deepseek-v4-flash"),
):
    from spiderpilot.config_store import save_config
    save_config({"api_key": api_key, "api_base": api_base, "model": model})
    return RedirectResponse("/settings", status_code=303)
