"""Spec models and loading helpers.

This module intentionally avoids pydantic for the MVP so SpiderPilot can run in
minimal Python environments. Validation is explicit and lightweight.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml


@dataclass
class ExpectedValue:
    equals: Any | None = None
    contains: list[Any] | None = None
    contains_any: list[Any] | None = None

    @classmethod
    def from_data(cls, data: Any) -> "ExpectedValue":
        if not isinstance(data, dict):
            data = {"equals": data}
        value = cls(
            equals=data.get("equals"),
            contains=data.get("contains"),
            contains_any=data.get("contains_any"),
        )
        if value.equals is None and not value.contains and not value.contains_any:
            raise ValueError("expected matcher must define one of: equals, contains, contains_any")
        return value


@dataclass
class SampleSpec:
    id: str
    url: str
    expected: dict[str, ExpectedValue] = field(default_factory=dict)

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "SampleSpec":
        if not isinstance(data, dict):
            raise ValueError("sample must be a mapping")
        sample_id = data.get("id")
        url = data.get("url")
        if not sample_id:
            raise ValueError("sample.id is required")
        if not _is_valid_http_url(url):
            raise ValueError(f"sample.url must be http/https URL: {url!r}")
        expected_raw = data.get("expected") or {}
        if not isinstance(expected_raw, dict):
            raise ValueError("sample.expected must be a mapping")
        expected = {name: ExpectedValue.from_data(value) for name, value in expected_raw.items()}
        return cls(id=str(sample_id), url=str(url), expected=expected)


@dataclass
class FieldSpec:
    type: str = "string"
    required: bool = False
    description: str | None = None
    normalize: str | None = None

    @classmethod
    def from_data(cls, data: Any) -> "FieldSpec":
        if data is None:
            data = {}
        if isinstance(data, str):
            data = {"type": data}
        if not isinstance(data, dict):
            raise ValueError("field spec must be a mapping or string")
        return cls(
            type=str(data.get("type", "string")),
            required=bool(data.get("required", False)),
            description=data.get("description"),
            normalize=data.get("normalize"),
        )


@dataclass
class CrawlSpec:
    version: int
    name: str
    target_type: str
    samples: list[SampleSpec]
    fields: dict[str, FieldSpec]

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "CrawlSpec":
        if not isinstance(data, dict):
            raise ValueError("spec must be a mapping")
        name = data.get("name")
        if not name:
            raise ValueError("spec.name is required")
        samples_raw = data.get("samples") or []
        fields_raw = data.get("fields") or {}
        if not isinstance(samples_raw, list) or not samples_raw:
            raise ValueError("spec.samples must include at least one sample")
        if not isinstance(fields_raw, dict) or not fields_raw:
            raise ValueError("spec.fields must define at least one field")
        samples = [SampleSpec.from_data(sample) for sample in samples_raw]
        fields = {name: FieldSpec.from_data(value) for name, value in fields_raw.items()}

        sample_ids = [sample.id for sample in samples]
        if len(sample_ids) != len(set(sample_ids)):
            raise ValueError("sample ids must be unique")
        unknown_expected = sorted(
            {
                field_name
                for sample in samples
                for field_name in sample.expected.keys()
                if field_name not in fields
            }
        )
        if unknown_expected:
            raise ValueError(f"expected contains fields not defined in fields: {', '.join(unknown_expected)}")

        return cls(
            version=int(data.get("version", 1)),
            name=str(name),
            target_type=str(data.get("target_type", "detail")),
            samples=samples,
            fields=fields,
        )


@dataclass
class TaskWorkspace:
    task_name: str
    spec_path: Path
    artifacts_dir: Path
    plan_path: Path
    generated_spider_path: Path
    result_path: Path
    summary_path: Path


def load_spec(path: Path) -> CrawlSpec:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return CrawlSpec.from_data(data)


def prepare_task_workspace(spec: CrawlSpec, source_path: Path, workspace: Path = Path("workspace")) -> TaskWorkspace:
    specs_dir = workspace / "specs"
    artifacts_dir = workspace / "artifacts" / spec.name
    plans_dir = workspace / "plans"
    generated_dir = workspace / "generated_spiders"
    results_dir = workspace / "results"

    for directory in [specs_dir, artifacts_dir, plans_dir, generated_dir, results_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    for sample in spec.samples:
        (artifacts_dir / sample.id).mkdir(parents=True, exist_ok=True)

    spec_path = specs_dir / f"{spec.name}.yaml"
    if source_path.resolve() != spec_path.resolve():
        shutil.copyfile(source_path, spec_path)

    return TaskWorkspace(
        task_name=spec.name,
        spec_path=spec_path,
        artifacts_dir=artifacts_dir,
        plan_path=plans_dir / f"{spec.name}.yaml",
        generated_spider_path=generated_dir / f"{spec.name}.py",
        result_path=results_dir / f"{spec.name}.json",
        summary_path=artifacts_dir / "summary.yaml",
    )


def build_task_summary(spec: CrawlSpec, workspace: TaskWorkspace) -> dict[str, Any]:
    return {
        "task": spec.name,
        "target_type": spec.target_type,
        "samples_total": len(spec.samples),
        "fields_total": len(spec.fields),
        "sample_ids": [sample.id for sample in spec.samples],
        "fields": list(spec.fields.keys()),
        "workspace": {
            "spec_path": str(workspace.spec_path),
            "artifacts_dir": str(workspace.artifacts_dir),
            "plan_path": str(workspace.plan_path),
            "generated_spider_path": str(workspace.generated_spider_path),
            "result_path": str(workspace.result_path),
        },
        "next_steps": [
            "antibot precheck",
            "probe",
            "reverse",
            "plan",
            "generate",
            "run/validate",
            "repair if needed",
        ],
    }


def write_task_summary(summary: dict[str, Any], path: Path) -> None:
    path.write_text(yaml.safe_dump(summary, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _is_valid_http_url(url: Any) -> bool:
    if not isinstance(url, str):
        return False
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
