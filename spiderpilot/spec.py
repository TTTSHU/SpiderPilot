"""Spec models and loading helpers."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, HttpUrl, model_validator


class ExpectedValue(BaseModel):
    """Expected sample value matcher."""

    equals: Any | None = None
    contains: list[Any] | None = None
    contains_any: list[Any] | None = None

    @model_validator(mode="after")
    def validate_matcher(self) -> "ExpectedValue":
        if self.equals is None and not self.contains and not self.contains_any:
            raise ValueError("expected matcher must define one of: equals, contains, contains_any")
        return self


class SampleSpec(BaseModel):
    id: str
    url: HttpUrl
    expected: dict[str, ExpectedValue] = Field(default_factory=dict)


class FieldSpec(BaseModel):
    type: str = "string"
    required: bool = False
    description: str | None = None
    normalize: str | None = None


class CrawlSpec(BaseModel):
    version: int = 1
    name: str
    target_type: str = "detail"
    samples: list[SampleSpec]
    fields: dict[str, FieldSpec]

    @model_validator(mode="after")
    def validate_spec(self) -> "CrawlSpec":
        if not self.samples:
            raise ValueError("spec must include at least one sample")
        if not self.fields:
            raise ValueError("spec must define at least one field")
        sample_ids = [sample.id for sample in self.samples]
        if len(sample_ids) != len(set(sample_ids)):
            raise ValueError("sample ids must be unique")
        unknown_expected = sorted(
            {
                field
                for sample in self.samples
                for field in sample.expected.keys()
                if field not in self.fields
            }
        )
        if unknown_expected:
            raise ValueError(f"expected contains fields not defined in fields: {', '.join(unknown_expected)}")
        return self


class TaskWorkspace(BaseModel):
    task_name: str
    spec_path: Path
    artifacts_dir: Path
    plan_path: Path
    generated_spider_path: Path
    result_path: Path
    summary_path: Path


def load_spec(path: Path) -> CrawlSpec:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return CrawlSpec.model_validate(data)


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
