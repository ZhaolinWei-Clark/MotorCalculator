"""FEMM solver availability detection.

Detection is read-only. This module never installs, downloads or modifies
anything; it only reports what is already present on the machine. A packaged
MotorCalculator build must import and run this module successfully on a machine
with no FEA software at all.
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

FEMM_AVAILABILITY_PROBE_VERSION = "phase10a.femm.probe.v1"

#: Executable names FEMM ships under, newest naming first.
FEMM_EXECUTABLE_NAMES = ("femm.exe", "femm42.exe", "femm")

#: Directories FEMM is conventionally installed into on Windows. Probed in
#: order; the first hit wins. ``%ProgramFiles%`` variants are resolved from the
#: environment so a non-``C:`` system drive still works.
FEMM_INSTALL_SUBDIRECTORIES = (
    ("femm42", "bin"),
    ("femm42",),
    ("FEMM", "bin"),
    ("FEMM",),
)

#: Python interfaces to FEMM, in the order we would prefer to use them.
FEMM_PYTHON_MODULE_CANDIDATES = ("femm", "pyfemm")


class FEMMAvailability(str, Enum):
    """The single availability verdict Phase 10A reports."""

    FEMM_AVAILABLE = "FEMM_AVAILABLE"
    FEMM_NOT_INSTALLED = "FEMM_NOT_INSTALLED"


class FEMMIntegrationPath(str, Enum):
    """How the adapter would drive FEMM if it were present."""

    SUBPROCESS_LUA = "SUBPROCESS_LUA"
    PYTHON_MODULE = "PYTHON_MODULE"
    NONE = "NONE"


@dataclass(frozen=True)
class FEMMAvailabilityReport:
    """Everything the probe learned, including where it looked and found nothing."""

    availability: FEMMAvailability
    integration_path: FEMMIntegrationPath
    executable_path: Path | None
    python_module_name: str | None
    searched_locations: tuple[str, ...]
    probe_version: str
    platform: str
    detail: str

    @property
    def is_available(self) -> bool:
        return self.availability is FEMMAvailability.FEMM_AVAILABLE

    @property
    def execution_blocked(self) -> bool:
        """True when a real solve cannot be attempted on this machine."""

        return not self.is_available


def _program_files_roots() -> tuple[Path, ...]:
    roots: list[Path] = []
    for variable in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        raw = os.environ.get(variable)
        if raw:
            roots.append(Path(raw))
    # A conventional FEMM install also lands directly on the system drive.
    system_drive = os.environ.get("SystemDrive")
    if system_drive:
        roots.append(Path(system_drive + os.sep))
    unique: list[Path] = []
    for root in roots:
        if root not in unique:
            unique.append(root)
    return tuple(unique)


def _candidate_executables() -> tuple[Path, ...]:
    candidates: list[Path] = []
    for root in _program_files_roots():
        for parts in FEMM_INSTALL_SUBDIRECTORIES:
            directory = root.joinpath(*parts)
            for name in FEMM_EXECUTABLE_NAMES:
                candidates.append(directory / name)
    return tuple(candidates)


def _find_python_module() -> str | None:
    import importlib.util

    for name in FEMM_PYTHON_MODULE_CANDIDATES:
        try:
            if importlib.util.find_spec(name) is not None:
                return name
        except (ImportError, ValueError):
            # A broken or shadowed distribution must not break detection.
            continue
    return None


def detect_femm(*, environment_override: str | None = None) -> FEMMAvailabilityReport:
    """Probe this machine for FEMM.

    ``environment_override`` (default: the ``MOTORCALC_FEMM_EXE`` environment
    variable) lets a user point at a non-standard install without any code
    change. The override is only honoured when it names an existing file.
    """

    searched: list[str] = []
    override = environment_override
    if override is None:
        override = os.environ.get("MOTORCALC_FEMM_EXE")
    if override:
        searched.append(f"override:{override}")
        override_path = Path(override)
        if override_path.is_file():
            return FEMMAvailabilityReport(
                availability=FEMMAvailability.FEMM_AVAILABLE,
                integration_path=FEMMIntegrationPath.SUBPROCESS_LUA,
                executable_path=override_path.resolve(),
                python_module_name=_find_python_module(),
                searched_locations=tuple(searched),
                probe_version=FEMM_AVAILABILITY_PROBE_VERSION,
                platform=sys.platform,
                detail="FEMM located through an explicit environment override.",
            )

    for name in FEMM_EXECUTABLE_NAMES:
        searched.append(f"PATH:{name}")
        found = shutil.which(name)
        if found:
            return FEMMAvailabilityReport(
                availability=FEMMAvailability.FEMM_AVAILABLE,
                integration_path=FEMMIntegrationPath.SUBPROCESS_LUA,
                executable_path=Path(found).resolve(),
                python_module_name=_find_python_module(),
                searched_locations=tuple(searched),
                probe_version=FEMM_AVAILABILITY_PROBE_VERSION,
                platform=sys.platform,
                detail="FEMM located on PATH.",
            )

    for candidate in _candidate_executables():
        searched.append(str(candidate))
        if candidate.is_file():
            return FEMMAvailabilityReport(
                availability=FEMMAvailability.FEMM_AVAILABLE,
                integration_path=FEMMIntegrationPath.SUBPROCESS_LUA,
                executable_path=candidate.resolve(),
                python_module_name=_find_python_module(),
                searched_locations=tuple(searched),
                probe_version=FEMM_AVAILABILITY_PROBE_VERSION,
                platform=sys.platform,
                detail="FEMM located in a conventional Windows install directory.",
            )

    module_name = _find_python_module()
    if module_name is not None:
        searched.append(f"python:{module_name}")
        # The Python interface still shells out to a real FEMM install, so a
        # module without an executable is reported as an integration path but
        # not as a usable solver.
        return FEMMAvailabilityReport(
            availability=FEMMAvailability.FEMM_NOT_INSTALLED,
            integration_path=FEMMIntegrationPath.PYTHON_MODULE,
            executable_path=None,
            python_module_name=module_name,
            searched_locations=tuple(searched),
            probe_version=FEMM_AVAILABILITY_PROBE_VERSION,
            platform=sys.platform,
            detail=(
                f"The {module_name} Python interface is importable but no FEMM "
                "executable was found; the interface cannot solve on its own."
            ),
        )
    searched.extend(f"python:{name}" for name in FEMM_PYTHON_MODULE_CANDIDATES)

    return FEMMAvailabilityReport(
        availability=FEMMAvailability.FEMM_NOT_INSTALLED,
        integration_path=FEMMIntegrationPath.NONE,
        executable_path=None,
        python_module_name=None,
        searched_locations=tuple(searched),
        probe_version=FEMM_AVAILABILITY_PROBE_VERSION,
        platform=sys.platform,
        detail="No FEMM executable and no FEMM Python interface were found.",
    )
