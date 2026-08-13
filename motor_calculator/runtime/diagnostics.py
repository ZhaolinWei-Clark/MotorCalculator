"""Local-only diagnostic export with restrained, non-project metadata."""

from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Iterable

from motor_calculator.i18n import get_locale
from motor_calculator.project import PROJECT_SCHEMA_VERSION
from motor_calculator.version import (
    APPLICATION_NAME,
    APPLICATION_VERSION,
    RELEASE_CHANNEL,
    get_git_commit,
)

from .paths import RuntimePaths, resolve_runtime_paths


def _load_packaged_build_info(paths: RuntimePaths) -> dict[str, object]:
    path = paths.resource("build_info.json")
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def build_diagnostics(
    paths: RuntimePaths | None = None,
    *,
    recent_errors: Iterable[str] = (),
) -> dict[str, object]:
    runtime_paths = paths or resolve_runtime_paths()
    build_info = _load_packaged_build_info(runtime_paths)
    build_commit = build_info.get("git_commit")
    if build_commit is None and runtime_paths.mode == "source":
        build_commit = get_git_commit(runtime_paths.application_root)
    return {
        "application": APPLICATION_NAME,
        "application_version": APPLICATION_VERSION,
        "release_channel": RELEASE_CHANNEL,
        "build_commit": build_commit,
        "os": platform.platform(),
        "architecture": platform.machine(),
        "python_runtime": platform.python_version(),
        "locale": get_locale(),
        "runtime_mode": runtime_paths.mode,
        "log_path": str(runtime_paths.log_file),
        "project_schema_version": PROJECT_SCHEMA_VERSION,
        "recent_non_sensitive_errors": [str(item) for item in recent_errors],
    }


def export_diagnostics(destination: str | Path, paths: RuntimePaths | None = None) -> Path:
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(build_diagnostics(paths), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target
