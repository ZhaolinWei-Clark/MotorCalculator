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

#: Bumped by Phase 10B. The v1 probe searched only PATH, the conventional
#: install directories and the Python interfaces. Preparing the first real
#: bring-up showed that a relocated install would have been reported as absent,
#: so v2 also consults the Windows registry (App Paths and the uninstall
#: entries), the ``.fem`` file association, the per-user ``Programs`` directory,
#: and every fixed drive root.
FEMM_AVAILABILITY_PROBE_VERSION = "phase10b.femm.probe.v2"

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

#: Registry locations that name an installed FEMM directly. ``App Paths`` is the
#: canonical Windows answer to "where is this program", and FEMM's installer
#: also writes an uninstall entry carrying ``InstallLocation``.
FEMM_REGISTRY_APP_PATHS = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\femm.exe",
    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\femm.exe",
)

FEMM_REGISTRY_UNINSTALL_ROOTS = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
)

#: Substring identifying a FEMM uninstall entry. Deliberately narrow: a looser
#: pattern such as "opera" matches "Autodesk Interoperability Engine Manager",
#: which is not an FEA solver. A false positive here would send the adapter at
#: an unrelated executable.
FEMM_UNINSTALL_DISPLAY_NAME_TOKEN = "femm"

#: Extensions whose registered handler would point at the FEMM executable.
FEMM_ASSOCIATED_EXTENSIONS = (".fem",)


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


def _fixed_drive_roots() -> tuple[Path, ...]:
    """Every fixed drive root, so a non-system-drive install is still found.

    FEMM's installer defaults to a drive-root directory, and a user with a
    second drive routinely relocates it there.
    """

    roots: list[Path] = []
    if sys.platform != "win32":
        return ()
    try:
        import string

        for letter in string.ascii_uppercase:
            root = Path(f"{letter}:{os.sep}")
            if root.is_dir():
                roots.append(root)
    except OSError:
        # An unreadable or disconnected drive must not break detection.
        return ()
    return tuple(roots)


def _program_files_roots() -> tuple[Path, ...]:
    roots: list[Path] = []
    for variable in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        raw = os.environ.get(variable)
        if raw:
            roots.append(Path(raw))
    # Modern per-user installs land under %LOCALAPPDATA%\Programs.
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        roots.append(Path(local_app_data) / "Programs")
    # A conventional FEMM install also lands directly on a drive root, and not
    # necessarily the system drive.
    system_drive = os.environ.get("SystemDrive")
    if system_drive:
        roots.append(Path(system_drive + os.sep))
    roots.extend(_fixed_drive_roots())
    unique: list[Path] = []
    for root in roots:
        if root not in unique:
            unique.append(root)
    return tuple(unique)


def _registry_candidates() -> tuple[Path, ...]:
    """Executable paths named by the Windows registry.

    Read-only, and defensive: a missing key, a denied read or a non-Windows
    platform yields no candidates rather than an error, because detection
    failing closed is correct while detection crashing is not.
    """

    if sys.platform != "win32":
        return ()
    try:
        import winreg
    except ImportError:
        return ()

    candidates: list[Path] = []

    def _read_value(root, subkey: str, name: str) -> str | None:
        for access in (winreg.KEY_READ, winreg.KEY_READ | winreg.KEY_WOW64_64KEY):
            try:
                with winreg.OpenKey(root, subkey, 0, access) as key:
                    value, _kind = winreg.QueryValueEx(key, name)
                    text = str(value).strip().strip('"')
                    return text or None
            except OSError:
                continue
        return None

    for subkey in FEMM_REGISTRY_APP_PATHS:
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            value = _read_value(root, subkey, "")
            if value:
                candidates.append(Path(value))

    for uninstall_root in FEMM_REGISTRY_UNINSTALL_ROOTS:
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(root, uninstall_root) as key:
                    count = winreg.QueryInfoKey(key)[0]
            except OSError:
                continue
            for index in range(count):
                try:
                    with winreg.OpenKey(root, uninstall_root) as key:
                        entry = winreg.EnumKey(key, index)
                except OSError:
                    continue
                subkey = f"{uninstall_root}\\{entry}"
                display = _read_value(root, subkey, "DisplayName") or ""
                if FEMM_UNINSTALL_DISPLAY_NAME_TOKEN not in display.lower():
                    continue
                location = _read_value(root, subkey, "InstallLocation")
                if not location:
                    continue
                directory = Path(location)
                for parts in ((), ("bin",)):
                    for name in FEMM_EXECUTABLE_NAMES:
                        candidates.append(directory.joinpath(*parts) / name)

    for extension in FEMM_ASSOCIATED_EXTENSIONS:
        handler = _read_value(winreg.HKEY_CLASSES_ROOT, extension, "")
        if not handler:
            continue
        command = _read_value(
            winreg.HKEY_CLASSES_ROOT, f"{handler}\\shell\\open\\command", ""
        )
        if not command:
            continue
        # A shell command looks like: "C:\path\femm.exe" "%1"
        executable = command.split('"')[1] if command.startswith('"') else command.split(" ")[0]
        if executable:
            candidates.append(Path(executable))

    unique: list[Path] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
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

    # The registry is consulted before the directory sweep: it names the install
    # the user actually performed, rather than guessing at a conventional path.
    for candidate in _registry_candidates():
        searched.append(f"registry:{candidate}")
        if candidate.is_file():
            return FEMMAvailabilityReport(
                availability=FEMMAvailability.FEMM_AVAILABLE,
                integration_path=FEMMIntegrationPath.SUBPROCESS_LUA,
                executable_path=candidate.resolve(),
                python_module_name=_find_python_module(),
                searched_locations=tuple(searched),
                probe_version=FEMM_AVAILABILITY_PROBE_VERSION,
                platform=sys.platform,
                detail="FEMM located through a Windows registry entry.",
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
