"""Offline signer verifier MVP."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml

from spiderpilot.spec import load_spec


def verify_signer(spec_path: Path, workspace: Path = Path("workspace")) -> dict[str, Any]:
    spec = load_spec(spec_path)
    sig_dir = workspace / "signatures" / spec.name
    manifest = _load_yaml(sig_dir / "signature.yaml")
    samples = json.loads((sig_dir / "samples.json").read_text(encoding="utf-8")) if (sig_dir / "samples.json").exists() else []
    signer_path = Path(manifest.get("signer_path") or sig_dir / "signer_stub.js")
    results = []
    for sample in samples:
        output = _run_node_signer(signer_path, _input_from_sample(sample))
        expected_value = sample.get("value")
        location = sample.get("location")
        key = sample.get("key")
        actual_value = None
        if location == "query":
            actual_value = (output.get("query") or {}).get(key)
        elif location in {"request_header", "header"}:
            actual_value = (output.get("headers") or {}).get(key)
        ok = str(actual_value) == str(expected_value)
        results.append({"sample_id": sample.get("sample_id"), "key": key, "location": location, "ok": ok, "expected": expected_value, "actual": actual_value})
    report = {"version": 1, "task": spec.name, "ok": all(r["ok"] for r in results) if results else False, "samples_total": len(results), "samples_passed": sum(1 for r in results if r["ok"]), "results": results}
    (sig_dir / "verify_report.yaml").write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return report


def _run_node_signer(signer_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("node executable is required for signature verification")
    proc = subprocess.run([node, str(signer_path)], input=json.dumps(payload), capture_output=True, text=True, timeout=20)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"signer exited with {proc.returncode}")
    return json.loads(proc.stdout or "{}")


def _input_from_sample(sample: dict[str, Any]) -> dict[str, Any]:
    return {"url": sample.get("url"), "method": "GET", "query": {}, "headers": {}, "body": None, "timestamp": None}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
