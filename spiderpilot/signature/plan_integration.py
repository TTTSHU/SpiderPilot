"""Integrate signature manifest into Extraction Plan."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from spiderpilot.spec import load_spec


def integrate_signature_plan(spec_path: Path, workspace: Path = Path("workspace")) -> dict[str, Any]:
    spec = load_spec(spec_path)
    plan_path = workspace / "plans" / f"{spec.name}.yaml"
    plan = yaml.safe_load(plan_path.read_text(encoding="utf-8")) if plan_path.exists() else {"version": 1, "name": spec.name}
    sig_dir = workspace / "signatures" / spec.name
    manifest_path = sig_dir / "signature.yaml"
    verify_path = sig_dir / "verify_report.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    verify = yaml.safe_load(verify_path.read_text(encoding="utf-8")) if verify_path.exists() else {}
    groups = manifest.get("groups") or []
    plan["signature"] = {
        "required": bool(groups),
        "kind": manifest.get("kind"),
        "manifest": str(manifest_path) if manifest_path.exists() else None,
        "signer": manifest.get("signer_path"),
        "verify_report": str(verify_path) if verify_path.exists() else None,
        "verify_ok": verify.get("ok"),
        "groups": [
            {"location": g.get("location"), "key": g.get("key"), "classification": g.get("classification")}
            for g in groups
        ],
    }
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(yaml.safe_dump(plan, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return plan
