"""CloakBrowser probe interface.

CloakBrowser integration is intentionally optional. This module records whether
CloakBrowser is installed and prepares the artifact schema used by the future
Network/HAR capture implementation.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from spiderpilot.probe.cloak_cdp import capture_with_cloakbrowser
from spiderpilot.spec import load_spec


@dataclass
class CloakBrowserStatus:
    available: bool
    executable: str | None
    info: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "executable": self.executable,
            "info": self.info,
            "error": self.error,
        }


def check_cloakbrowser() -> CloakBrowserStatus:
    try:
        from cloakbrowser import launch  # noqa: F401
        exe = shutil.which("cloakbrowser")
        return CloakBrowserStatus(True, exe or "cloakbrowser (imported)", info="Module import successful")
    except ImportError:
        return CloakBrowserStatus(False, None, error="cloakbrowser Python module not installed")
    except Exception as exc:
        return CloakBrowserStatus(False, None, error=f"{type(exc).__name__}: {exc}")


def run_cloak_probe(spec_path: Path, workspace: Path = Path("workspace"), capture: bool = False, wait_seconds: float = 15.0, signature_hook: bool = False, headless: bool = True, stealth: bool = True) -> dict[str, Any]:
    spec = load_spec(spec_path)
    status = check_cloakbrowser()
    artifact_root = workspace / "artifacts" / spec.name
    artifact_root.mkdir(parents=True, exist_ok=True)
    samples = []
    for sample in spec.samples:
        sample_dir = artifact_root / sample.id / "cloak"
        sample_dir.mkdir(parents=True, exist_ok=True)
        placeholder = {
            "sample_id": sample.id,
            "url": sample.url,
            "status": "pending_network_capture" if status.available else "unavailable",
            "planned_files": {
                "rendered_html": str(sample_dir / "rendered.html"),
                "screenshot": str(sample_dir / "screenshot.png"),
                "network_har": str(sample_dir / "network.har"),
                "cookies": str(sample_dir / "cookies.json"),
                "storage": str(sample_dir / "storage.json"),
                "responses_dir": str(sample_dir / "responses"),
            },
        }
        if capture and status.available:
            try:
                placeholder["capture"] = capture_with_cloakbrowser(sample.url, sample_dir, wait_seconds=wait_seconds)
                placeholder["status"] = "captured"
            except Exception as exc:
                placeholder["status"] = "capture_failed"
                placeholder["error"] = f"{type(exc).__name__}: {exc}"
        (sample_dir / "cloak_meta.yaml").write_text(yaml.safe_dump(placeholder, allow_unicode=True, sort_keys=False), encoding="utf-8")
        samples.append(placeholder)
    report = {"version": 1, "task": spec.name, "cloakbrowser": status.to_dict(), "samples": samples}
    report_path = artifact_root / "cloak_probe_report.yaml"
    report_path.write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return report
