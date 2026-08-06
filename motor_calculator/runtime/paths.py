"""Centralized application, bundled-resource, and mutable user-data paths."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


USER_DATA_ENVIRONMENT_VARIABLE = "MOTOR_CALCULATOR_USER_DATA"


@dataclass(frozen=True)
class RuntimePaths:
    mode: str
    application_root: Path
    resource_root: Path
    user_data_dir: Path
    feedback_store: Path
    log_dir: Path
    log_file: Path
    export_dir: Path
    cache_dir: Path

    def resource(self, *parts: str) -> Path:
        return self.resource_root.joinpath(*parts)


@dataclass(frozen=True)
class ResourceIntegrityCheck:
    name: str
    path: Path
    required: bool
    available: bool


def _default_user_data_root(
    environment: Mapping[str, str],
    *,
    platform_name: str,
    home_dir: Path,
) -> Path:
    override = environment.get(USER_DATA_ENVIRONMENT_VARIABLE)
    if override:
        return Path(override).expanduser()
    if platform_name == "win32":
        local_app_data = environment.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else home_dir / "AppData" / "Local"
        return base / "MotorCalculator"
    xdg_data_home = environment.get("XDG_DATA_HOME")
    base = Path(xdg_data_home) if xdg_data_home else home_dir / ".local" / "share"
    return base / "MotorCalculator"


def resolve_runtime_paths(
    *,
    environment: Mapping[str, str] | None = None,
    packaged: bool | None = None,
    executable_path: Path | None = None,
    bundle_root: Path | None = None,
    source_root: Path | None = None,
    platform_name: str | None = None,
    home_dir: Path | None = None,
) -> RuntimePaths:
    """Resolve paths without relying on the process current working directory."""

    env = os.environ if environment is None else environment
    is_packaged = bool(getattr(sys, "frozen", False)) if packaged is None else packaged
    platform_value = sys.platform if platform_name is None else platform_name
    home = Path.home() if home_dir is None else Path(home_dir)
    if is_packaged:
        executable = Path(sys.executable if executable_path is None else executable_path).resolve()
        application_root = executable.parent
        detected_bundle = getattr(sys, "_MEIPASS", application_root)
        resource_root = Path(detected_bundle if bundle_root is None else bundle_root).resolve()
        mode = "packaged"
    else:
        application_root = Path(source_root).resolve() if source_root is not None else Path(__file__).resolve().parents[2]
        resource_root = application_root
        mode = "source"

    user_data_dir = _default_user_data_root(
        env,
        platform_name=platform_value,
        home_dir=home,
    ).resolve()
    log_dir = user_data_dir / "logs"
    return RuntimePaths(
        mode=mode,
        application_root=application_root,
        resource_root=resource_root,
        user_data_dir=user_data_dir,
        feedback_store=user_data_dir / "validation_feedback" / "feedback_records.jsonl",
        log_dir=log_dir,
        log_file=log_dir / "app.log",
        export_dir=user_data_dir / "exports",
        cache_dir=user_data_dir / "cache",
    )


def create_runtime_directories(paths: RuntimePaths) -> RuntimePaths:
    """Create mutable directories, but keep feedback storage lazy."""

    for directory in (paths.user_data_dir, paths.log_dir, paths.export_dir, paths.cache_dir):
        directory.mkdir(parents=True, exist_ok=True)
    return paths


def check_packaged_resources(paths: RuntimePaths) -> tuple[ResourceIntegrityCheck, ...]:
    """Describe resources needed by the GUI without silently accepting omissions."""

    definitions = (
        ("legacy_gui_module", ("motor_calculator", "PMDC_Calculator_claude204.py"), True),
        (
            "controlled_uncertainty_specification",
            ("validation_data", "uncertainty", "phase7i_afpm_back_emf_uncertainty.json"),
            False,
        ),
        (
            "controlled_fea_reference",
            ("validation_data", "fea_reference", "phase7h_controlled_ssdr_machine.json"),
            False,
        ),
    )
    return tuple(
        ResourceIntegrityCheck(name, paths.resource(*parts), required, paths.resource(*parts).is_file())
        for name, parts, required in definitions
    )
