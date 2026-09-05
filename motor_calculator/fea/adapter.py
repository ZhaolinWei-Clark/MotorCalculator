"""Solver adapters: the FEMM subprocess driver and the mock pipeline solver.

Subprocess safety
-----------------
The FEMM adapter never uses a shell. It invokes an explicit, verified executable
path with an argument list, inside a dedicated working directory under the
user's own data area, with a timeout and full capture of exit code, stdout and
stderr. Nothing that reaches this module can be turned into a shell command.

Mock safety
-----------
:class:`MockFEASolver` exists so the *software* pipeline can be tested without a
solver. It stamps ``is_mock=True`` into provenance, and every consumer refuses
to treat such a result as validation evidence.
"""

from __future__ import annotations

import csv
import math
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .availability import FEMMAvailabilityReport, detect_femm
from .femm_lua import balanced_phase_currents, build_position_script
from .geometry import build_slice_model
from .hashing import compute_analytical_fingerprint
from .models import FEAValidationCase, FEAValidationTarget
from .results import (
    FEAPositionSample,
    FEARawResult,
    FEAResultProvenance,
    FEA_RESULT_SCHEMA_VERSION,
    utc_timestamp,
)

#: Wall-clock ceiling for a single FEMM position solve.
DEFAULT_POSITION_TIMEOUT_SECONDS = 600.0

#: Name of the working directory created under the user's data area.
FEA_WORKSPACE_DIRECTORY_NAME = "fea_workspace"

MOCK_SOLVER_NAME = "MOCK_FEA_SOLVER"

#: Recorded whenever the torque excitation angle could not be tied to a measured
#: no-load alignment. The result is still produced, but it is not silently
#: presented as an ``id = 0`` operating point.
UNVERIFIED_ALIGNMENT_WARNING = (
    "the electrical alignment between the phase-A axis and the rotor d-axis was "
    "assumed to be zero and not measured from a no-load sweep, so the excitation "
    "is not confirmed to be the id = 0 operating point the analytical torque "
    "constant is defined at"
)


class FEASolverExecutionError(RuntimeError):
    """Raised when a real solver run fails; never raised to hide a bad result."""


@dataclass(frozen=True)
class FEASolveOutcome:
    """Either a completed result, or an explicit statement of why there is none."""

    status: str
    result: FEARawResult | None
    detail: str
    workspace: Path | None
    seconds: float | None

    @property
    def succeeded(self) -> bool:
        return self.result is not None


class FEASolver(Protocol):
    """The minimal contract every solver adapter satisfies."""

    name: str

    def is_available(self) -> bool: ...

    def solve(self, case: FEAValidationCase) -> FEASolveOutcome: ...


def default_workspace_root() -> Path:
    """A dedicated user-space directory for solver scratch files.

    Never the repository, and never the project's existing ``tmp/``.
    """

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "MotorCalculator" / FEA_WORKSPACE_DIRECTORY_NAME
    return Path(tempfile.gettempdir()) / "MotorCalculator" / FEA_WORKSPACE_DIRECTORY_NAME


def _mesh_size_map(case: FEAValidationCase) -> dict[str, float]:
    policy = case.mesh_policy
    return {
        "global": policy.global_size_m,
        "air_gap": policy.air_gap_size_m,
        "magnet": policy.magnet_size_m,
        "magnet_edge": policy.magnet_edge_size_m,
        "slot_opening": policy.slot_opening_size_m or policy.air_gap_size_m,
        "winding": policy.winding_size_m,
        "core": policy.core_size_m or policy.global_size_m,
        "air_domain": policy.air_domain_size_m,
    }


def _operating_point_summary(case: FEAValidationCase) -> dict[str, float]:
    point = case.operating_point
    return {
        "mechanical_speed_rpm": point.mechanical_speed_rpm,
        "phase_current_rms_a": point.phase_current_rms_a,
        "current_angle_electrical_deg": point.current_angle_electrical_deg,
        "temperature_c": point.temperature_c,
        "rotor_angle_span_mech_deg": point.rotor_angle_span_mech_deg,
    }


def build_provenance(
    case: FEAValidationCase,
    *,
    solver: str,
    solver_version: str,
    is_mock: bool,
    element_count: int | None,
    solve_seconds: float | None,
    warnings: tuple[str, ...] = (),
) -> FEAResultProvenance:
    """Assemble the provenance every result must carry."""

    extraction = (
        case.back_emf_extraction_method
        if case.target is FEAValidationTarget.NO_LOAD_BACK_EMF
        else case.torque_extraction_method
    )
    return FEAResultProvenance(
        solver=solver,
        solver_version=solver_version,
        is_mock=is_mock,
        case_id=case.case_id,
        analytical_fingerprint=compute_analytical_fingerprint(case),
        schema_version=FEA_RESULT_SCHEMA_VERSION,
        mesh_policy_name=case.mesh_policy.name,
        requested_mesh_sizes_m=_mesh_size_map(case),
        reported_element_count=element_count,
        symmetry_applied=case.symmetry.applied,
        sector_fraction=case.symmetry.sector_fraction,
        sample_count=case.operating_point.rotor_angle_sample_count,
        extraction_method=extraction,
        material_assumptions=case.materials.property_mismatches,
        operating_point_summary=_operating_point_summary(case),
        timestamp_utc=utc_timestamp(),
        solve_seconds=solve_seconds,
        warnings=warnings,
    )


def generate_case_scripts(
    case: FEAValidationCase,
    workspace: Path,
    *,
    electrical_alignment_offset_deg: float = 0.0,
) -> tuple[Path, ...]:
    """Write one Lua script per rotor position. Requires no FEMM installation."""

    workspace.mkdir(parents=True, exist_ok=True)
    output_path = workspace / "fea_samples.csv"
    if output_path.exists():
        output_path.unlink()
    mesh_sizes = _mesh_size_map(case)
    scripts: list[Path] = []
    angles = case.operating_point.rotor_angles_mech_deg()
    phase_names = tuple(sorted(set(case.winding.coil_phase_assignment)))
    for index, angle in enumerate(angles):
        model = build_slice_model(
            case.geometry,
            slot_layers=case.winding.slot_layers(),
            mesh_sizes=mesh_sizes,
            symmetry=case.symmetry,
            rotor_angle_mech_deg=angle,
        )
        electrical_angle = case.geometry.pole_pairs * angle + electrical_alignment_offset_deg
        currents = balanced_phase_currents(
            phase_rms_a=case.operating_point.phase_current_rms_a,
            electrical_angle_deg=electrical_angle,
            current_angle_electrical_deg=case.operating_point.current_angle_electrical_deg,
            phase_names=phase_names,
        )
        script = build_position_script(
            case,
            model,
            phase_currents=currents,
            fem_path=str(workspace / f"position_{index:04d}.fem"),
            output_path=str(output_path),
            append=index > 0,
        )
        script_path = workspace / f"position_{index:04d}.lua"
        script_path.write_text(script, encoding="utf-8")
        scripts.append(script_path)
    return tuple(scripts)


def parse_samples_csv(path: Path, phase_names: tuple[str, ...]) -> tuple[FEAPositionSample, ...]:
    """Parse the CSV the generated Lua writes."""

    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = tuple(reader.fieldnames or ())
        required = ("rotor_angle_mech_deg", "circumferential_force_n")
        missing = tuple(name for name in required if name not in columns)
        if missing:
            raise FEASolverExecutionError(
                f"solver output is missing required columns: {', '.join(missing)}"
            )
        samples: list[FEAPositionSample] = []
        for row in reader:
            linkage = {}
            for name in phase_names:
                key = f"flux_linkage_{name}_wb_turn"
                if key not in columns:
                    raise FEASolverExecutionError(f"solver output is missing column {key}")
                linkage[name] = float(row[key])
            element_raw = (row.get("element_count") or "").strip()
            samples.append(
                FEAPositionSample(
                    rotor_angle_mech_deg=float(row["rotor_angle_mech_deg"]),
                    phase_flux_linkage_wb_turn=linkage,
                    circumferential_force_n=float(row["circumferential_force_n"]),
                    element_count=int(float(element_raw)) if element_raw else None,
                )
            )
    if not samples:
        raise FEASolverExecutionError("solver produced no samples")
    return tuple(samples)


class FEMMSubprocessSolver:
    """Drive a locally installed FEMM through generated Lua scripts."""

    name = "FEMM"

    def __init__(
        self,
        *,
        availability: FEMMAvailabilityReport | None = None,
        workspace_root: Path | None = None,
        timeout_seconds: float = DEFAULT_POSITION_TIMEOUT_SECONDS,
        keep_workspace: bool = False,
    ) -> None:
        self.availability = availability if availability is not None else detect_femm()
        self.workspace_root = workspace_root or default_workspace_root()
        self.timeout_seconds = timeout_seconds
        self.keep_workspace = keep_workspace

    def is_available(self) -> bool:
        return self.availability.is_available

    def _run_script(self, executable: Path, script: Path, workspace: Path) -> None:
        # No shell, explicit executable, explicit argument list, explicit cwd,
        # explicit timeout, full capture.
        try:
            completed = subprocess.run(  # noqa: S603 - explicit path, no shell
                [str(executable), "-lua-script=" + str(script), "-windowhide"],
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                shell=False,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise FEASolverExecutionError(
                f"FEMM exceeded the {self.timeout_seconds:.0f} s timeout on {script.name}"
            ) from error
        if completed.returncode != 0:
            raise FEASolverExecutionError(
                f"FEMM exited with code {completed.returncode} on {script.name}: "
                f"{completed.stderr.strip() or completed.stdout.strip()}"
            )

    def solve(
        self,
        case: FEAValidationCase,
        *,
        electrical_alignment_offset_deg: float | None = None,
    ) -> FEASolveOutcome:
        if not self.is_available():
            return FEASolveOutcome(
                status="BLOCKED_BY_ENVIRONMENT",
                result=None,
                detail=(
                    "FEMM is not installed on this machine, so no field solution was "
                    "attempted. The validation case and its solver scripts are still "
                    "generated and exportable."
                ),
                workspace=None,
                seconds=None,
            )
        executable = self.availability.executable_path
        assert executable is not None

        workspace = self.workspace_root / case.case_id[:16]
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True, exist_ok=True)

        warnings: list[str] = []
        offset = electrical_alignment_offset_deg
        if offset is None and case.target is FEAValidationTarget.AVERAGE_TORQUE:
            offset = 0.0
            warnings.append(UNVERIFIED_ALIGNMENT_WARNING)
        offset = offset or 0.0

        started = time.perf_counter()
        try:
            scripts = generate_case_scripts(
                case, workspace, electrical_alignment_offset_deg=offset
            )
            for script in scripts:
                self._run_script(executable, script, workspace)
            phase_names = tuple(sorted(set(case.winding.coil_phase_assignment)))
            samples = parse_samples_csv(workspace / "fea_samples.csv", phase_names)
        except FEASolverExecutionError as error:
            return FEASolveOutcome(
                status="FAILED",
                result=None,
                detail=str(error),
                workspace=workspace,
                seconds=time.perf_counter() - started,
            )
        seconds = time.perf_counter() - started

        element_counts = [s.element_count for s in samples if s.element_count is not None]
        result = FEARawResult(
            target=case.target,
            provenance=build_provenance(
                case,
                solver=self.name,
                solver_version=_probe_version(executable),
                is_mock=False,
                element_count=max(element_counts) if element_counts else None,
                solve_seconds=seconds,
                warnings=tuple(warnings),
            ),
            samples=samples,
            mechanical_speed_rpm=case.operating_point.mechanical_speed_rpm,
            mean_radius_m=case.geometry.mean_radius_m,
            pole_pairs=case.geometry.pole_pairs,
            span_mech_deg=case.operating_point.rotor_angle_span_mech_deg,
        )
        if not self.keep_workspace:
            # Remove only what this run created.
            for path in workspace.glob("position_*"):
                path.unlink(missing_ok=True)
        return FEASolveOutcome(
            status="SUCCESS",
            result=result,
            detail="FEMM completed every requested rotor position.",
            workspace=workspace,
            seconds=seconds,
        )


def _probe_version(executable: Path) -> str:
    """Best-effort solver version string, never fabricated."""

    try:
        parent = executable.parent
        for name in ("version.txt", "VERSION"):
            candidate = parent / name
            if candidate.is_file():
                text = candidate.read_text(encoding="utf-8", errors="replace").strip()
                if text:
                    return text
    except OSError:
        pass
    return "UNREPORTED_BY_INSTALLATION"


class MockFEASolver:
    """A deterministic stand-in used ONLY to exercise the software pipeline.

    The waveforms it returns are a smooth analytical placeholder, not a field
    solution. Its output is stamped ``is_mock=True`` and is rejected as evidence
    by :func:`motor_calculator.fea.comparison.build_comparison` and by the
    evidence layer.
    """

    name = MOCK_SOLVER_NAME

    def __init__(self, *, flux_linkage_peak_wb_turn: float = 0.01, force_amplitude_n: float = 1.0) -> None:
        self.flux_linkage_peak_wb_turn = flux_linkage_peak_wb_turn
        self.force_amplitude_n = force_amplitude_n

    def is_available(self) -> bool:
        return True

    def solve(self, case: FEAValidationCase) -> FEASolveOutcome:
        started = time.perf_counter()
        phase_names = tuple(sorted(set(case.winding.coil_phase_assignment)))
        angles = case.operating_point.rotor_angles_mech_deg()
        samples: list[FEAPositionSample] = []
        for angle in angles:
            electrical = math.radians(case.geometry.pole_pairs * angle)
            linkage = {
                name: self.flux_linkage_peak_wb_turn
                * math.cos(electrical - 2.0 * math.pi * index / len(phase_names))
                for index, name in enumerate(phase_names)
            }
            if case.target is FEAValidationTarget.COGGING_TORQUE:
                cycles = 2.0 * math.pi * angle / case.operating_point.rotor_angle_span_mech_deg
                force = self.force_amplitude_n * math.sin(cycles)
            else:
                force = self.force_amplitude_n
            samples.append(
                FEAPositionSample(
                    rotor_angle_mech_deg=angle,
                    phase_flux_linkage_wb_turn=linkage,
                    circumferential_force_n=force,
                    element_count=None,
                )
            )
        seconds = time.perf_counter() - started
        result = FEARawResult(
            target=case.target,
            provenance=build_provenance(
                case,
                solver=self.name,
                solver_version="mock-1",
                is_mock=True,
                element_count=None,
                solve_seconds=seconds,
                warnings=(
                    "MOCK DATA: this result is a software-pipeline placeholder and is "
                    "not a field solution; it must never be reported as validation evidence",
                ),
            ),
            samples=tuple(samples),
            mechanical_speed_rpm=case.operating_point.mechanical_speed_rpm,
            mean_radius_m=case.geometry.mean_radius_m,
            pole_pairs=case.geometry.pole_pairs,
            span_mech_deg=case.operating_point.rotor_angle_span_mech_deg,
        )
        return FEASolveOutcome(
            status="SUCCESS_MOCK",
            result=result,
            detail="Mock pipeline result; not validation evidence.",
            workspace=None,
            seconds=seconds,
        )
