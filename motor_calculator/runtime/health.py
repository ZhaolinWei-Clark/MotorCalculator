"""Structured runtime health checks for source and packaged execution."""

from __future__ import annotations

import importlib
import os
import platform
import sys
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

from motor_calculator.version import APPLICATION_VERSION, RUNTIME_SCHEMA_VERSION

from .paths import RuntimePaths, check_packaged_resources, resolve_runtime_paths


class HealthStatus(str, Enum):
    OK = "OK"
    WARNING = "WARNING"
    FAILED = "FAILED"


@dataclass(frozen=True)
class HealthCheck:
    name: str
    status: HealthStatus
    message: str
    critical: bool
    details: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class RuntimeHealthReport:
    schema_version: str
    application_version: str
    overall_status: HealthStatus
    checks: tuple[HealthCheck, ...]
    suggestions: tuple[str, ...]

    @property
    def critical_failures(self) -> tuple[HealthCheck, ...]:
        return tuple(check for check in self.checks if check.critical and check.status is HealthStatus.FAILED)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "application_version": self.application_version,
            "overall_status": self.overall_status.value,
            "checks": [
                {
                    "name": check.name,
                    "status": check.status.value,
                    "message": check.message,
                    "critical": check.critical,
                    "details": dict(check.details),
                }
                for check in self.checks
            ],
            "suggestions": list(self.suggestions),
        }


def probe_tk_runtime() -> tuple[str, str, str]:
    """Create and cleanly destroy a real Tk root, returning Tcl/Tk versions."""

    import tkinter as tk

    root = tk.Tk()
    try:
        root.withdraw()
        patchlevel = str(root.tk.call("info", "patchlevel"))
        tk_version = str(root.tk.call("package", "require", "Tk"))
        return patchlevel, tk_version, str(Path(tk.__file__).resolve())
    finally:
        root.destroy()


def _python_check() -> HealthCheck:
    supported = (3, 10) <= sys.version_info[:2] < (3, 14)
    return HealthCheck(
        "python",
        HealthStatus.OK if supported else HealthStatus.FAILED,
        "Python version is supported." if supported else "Python 3.10-3.13 is required.",
        True,
        (
            ("version", platform.python_version()),
            ("executable", sys.executable),
            ("architecture", platform.architecture()[0]),
            ("base_prefix", sys.base_prefix),
        ),
    )


def _module_check(module_name: str, *, critical: bool) -> HealthCheck:
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        return HealthCheck(
            module_name,
            HealthStatus.FAILED if critical else HealthStatus.WARNING,
            f"Import failed: {exc}",
            critical,
        )
    version = getattr(module, "__version__", "available")
    return HealthCheck(module_name, HealthStatus.OK, "Import succeeded.", critical, (("version", str(version)),))


def _tk_check(tk_probe: Callable[[], tuple[str, str, str]]) -> HealthCheck:
    try:
        tcl_version, tk_version, module_path = tk_probe()
    except Exception as exc:
        return HealthCheck(
            "tcl_tk_runtime",
            HealthStatus.FAILED,
            f"Tkinter runtime could not be initialized: {exc}",
            True,
            (("compiled_tcl_tk", "8.6 if tkinter import succeeds; runtime initialization failed"),),
        )
    return HealthCheck(
        "tcl_tk_runtime",
        HealthStatus.OK,
        "A Tk root was created and destroyed successfully.",
        True,
        (("tcl_patchlevel", tcl_version), ("tk_version", tk_version), ("module", module_path)),
    )


def _writable_user_data_check(paths: RuntimePaths) -> HealthCheck:
    probe = paths.user_data_dir / f".runtime-check-{uuid.uuid4().hex}.tmp"
    try:
        paths.user_data_dir.mkdir(parents=True, exist_ok=True)
        with probe.open("xb") as stream:
            stream.write(b"runtime-check")
            stream.flush()
            os.fsync(stream.fileno())
        probe.unlink()
    except OSError as exc:
        return HealthCheck("user_data", HealthStatus.FAILED, f"User-data directory is not writable: {exc}", True)
    finally:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
    return HealthCheck(
        "user_data",
        HealthStatus.OK,
        "User-data directory is writable.",
        True,
        (("path", str(paths.user_data_dir)),),
    )


def _feedback_check(paths: RuntimePaths) -> HealthCheck:
    path = paths.feedback_store
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            with path.open("rb") as stream:
                stream.read(1)
    except OSError as exc:
        return HealthCheck("feedback_database", HealthStatus.WARNING, f"Feedback store is inaccessible: {exc}", False)
    return HealthCheck(
        "feedback_database",
        HealthStatus.OK,
        "Feedback store is accessible or ready for lazy creation.",
        False,
        (("path", str(path)), ("exists", str(path.exists()).lower())),
    )


def _resource_checks(paths: RuntimePaths) -> tuple[HealthCheck, ...]:
    checks: list[HealthCheck] = []
    for resource in check_packaged_resources(paths):
        if resource.available:
            status = HealthStatus.OK
            message = "Resource is available."
        elif resource.required:
            status = HealthStatus.FAILED
            message = "Required application resource is missing."
        else:
            status = HealthStatus.WARNING
            message = "Optional validation resource is missing; confidence analysis will degrade gracefully."
        checks.append(
            HealthCheck(
                f"resource:{resource.name}",
                status,
                message,
                resource.required,
                (("path", str(resource.path)),),
            )
        )
    return tuple(checks)


def check_runtime_health(
    paths: RuntimePaths | None = None,
    *,
    tk_probe: Callable[[], tuple[str, str, str]] = probe_tk_runtime,
) -> RuntimeHealthReport:
    runtime_paths = paths or resolve_runtime_paths()
    checks = (
        _python_check(),
        _module_check("tkinter", critical=True),
        _tk_check(tk_probe),
        _module_check("numpy", critical=True),
        _module_check("matplotlib", critical=False),
        _module_check("motor_calculator.motor_core.calculations", critical=True),
        _writable_user_data_check(runtime_paths),
        _feedback_check(runtime_paths),
        *_resource_checks(runtime_paths),
    )
    if any(check.critical and check.status is HealthStatus.FAILED for check in checks):
        overall = HealthStatus.FAILED
    elif any(check.status is HealthStatus.WARNING for check in checks):
        overall = HealthStatus.WARNING
    else:
        overall = HealthStatus.OK
    suggestions: list[str] = []
    if any(check.name == "tcl_tk_runtime" and check.status is HealthStatus.FAILED for check in checks):
        suggestions.append(
            "Install a complete 64-bit Windows CPython distribution with Tcl/Tk, recreate .venv, and rerun work/check_tk_runtime.py."
        )
        suggestions.append("Do not hard-code TCL_LIBRARY or TK_LIBRARY unless the paths belong to that same Python installation.")
    return RuntimeHealthReport(
        RUNTIME_SCHEMA_VERSION,
        APPLICATION_VERSION,
        overall,
        checks,
        tuple(suggestions),
    )


def format_startup_failure(
    error: BaseException,
    paths: RuntimePaths,
    *,
    report: RuntimeHealthReport | None = None,
) -> str:
    health = report
    tcl_status = "FAILED"
    if health is not None:
        candidate = next((check for check in health.checks if check.name == "tcl_tk_runtime"), None)
        if candidate is not None:
            tcl_status = candidate.status.value
    log_label = "Detailed local log" if paths.log_file.exists() else "Local log target (if writable)"
    return "\n".join(
        (
            "GUI 启动失败：Tkinter runtime could not be initialized.",
            f"Detected Python: {platform.python_version()} ({sys.executable})",
            f"Detected Tcl/Tk status: {tcl_status}",
            f"Original error: {error}",
            "Remediation: install a complete Windows CPython with Tcl/Tk, recreate the virtual environment,",
            "then run: .venv\\Scripts\\python.exe work\\check_tk_runtime.py",
            "See README.md and docs/phase8a_windows_runtime_audit_zh.md for details.",
            f"{log_label}: {paths.log_file}",
        )
    )
