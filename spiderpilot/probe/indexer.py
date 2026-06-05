"""Probe artifact index utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def build_probe_index(task_name: str, artifact_root: Path) -> dict[str, Any]:
    samples = []
    for sample_dir in sorted(p for p in artifact_root.iterdir() if p.is_dir()):
        files = {
            "raw_html": str(sample_dir / "raw.html") if (sample_dir / "raw.html").exists() else None,
            "headers": str(sample_dir / "headers.json") if (sample_dir / "headers.json").exists() else None,
            "cookies": str(sample_dir / "cookies.json") if (sample_dir / "cookies.json").exists() else None,
            "meta": str(sample_dir / "meta.yaml") if (sample_dir / "meta.yaml").exists() else None,
            "json_responses": [str(p) for p in sorted((sample_dir / "responses").glob("*.json"))] if (sample_dir / "responses").exists() else [],
        }
        samples.append({"sample_id": sample_dir.name, "artifact_dir": str(sample_dir), "files": files})
    return {"version": 1, "task": task_name, "samples_total": len(samples), "samples": samples}


def write_probe_index(task_name: str, artifact_root: Path) -> dict[str, Any]:
    index = build_probe_index(task_name, artifact_root)
    path = artifact_root / "probe_index.yaml"
    path.write_text(yaml.safe_dump(index, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return index
