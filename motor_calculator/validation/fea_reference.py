"""Independent FEA reference metadata and convergence gates for validation only."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Protocol


class FEAFidelityTier(str, Enum):
    FEA_TIER_1 = "FEA_TIER_1"
    FEA_TIER_2 = "FEA_TIER_2"
    FEA_TIER_3 = "FEA_TIER_3"


class FEADimensionality(str, Enum):
    THREE_D = "3D"
    QUASI_THREE_D = "quasi_3D"
    TWO_D = "2D"
    AXISYMMETRIC = "axisymmetric"


class EvidenceClassification(str, Enum):
    INTERNAL_ANALYTICAL = "INTERNAL_ANALYTICAL"
    INDEPENDENT_FEA_REFERENCE = "INDEPENDENT_FEA_REFERENCE"
    PUBLISHED_FEA_REFERENCE = "PUBLISHED_FEA_REFERENCE"
    EXPERIMENTAL_MEASUREMENT = "EXPERIMENTAL_MEASUREMENT"


class FEAExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    IMPORTED_EXTERNAL = "IMPORTED_EXTERNAL"
    BLOCKED_BY_SOLVER_AVAILABILITY = "BLOCKED_BY_SOLVER_AVAILABILITY"
    FAILED = "FAILED"


@dataclass(frozen=True)
class FEASolverMetadata:
    solver: str
    solver_version: str
    model_version: str
    dimensionality: FEADimensionality
    fidelity_tier: FEAFidelityTier
    automation_path: str

    def __post_init__(self) -> None:
        for name in ("solver", "solver_version", "model_version", "automation_path"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must be explicit")


@dataclass(frozen=True)
class FEAReferenceGeometry:
    topology: str
    stator_count: int
    rotor_count: int
    active_air_gap_count: int
    inner_radius_m: float
    outer_radius_m: float
    physical_air_gap_per_side_m: float
    magnet_thickness_m: float
    pole_pairs: int
    magnet_arc_ratio: float
    rotor_support_thickness_m: float
    winding_axial_thickness_m: float
    air_domain_radial_margin_m: float
    air_domain_axial_margin_m: float


@dataclass(frozen=True)
class FEAReferenceMaterials:
    magnet_remanence_t: float
    magnet_relative_permeability: float
    magnet_conductivity_s_per_m: float
    conductor_material: str
    conductor_conductivity_s_per_m: float
    rotor_support_relative_permeability: float
    rotor_support_conductivity_s_per_m: float
    air_relative_permeability: float
    ferromagnetic_core_present: bool
    steel_bh_curve_source: str | None

    def __post_init__(self) -> None:
        if self.ferromagnetic_core_present and not self.steel_bh_curve_source:
            raise ValueError("ferromagnetic references require an explicit steel B-H curve source")
        if not self.ferromagnetic_core_present and self.steel_bh_curve_source is not None:
            raise ValueError("coreless references must not declare a steel B-H curve")


@dataclass(frozen=True)
class FEAReferenceWinding:
    phases: int
    total_coils: int
    turns_per_coil: int
    coils_per_phase: int
    series_coils_per_branch: int
    parallel_branches: int
    effective_series_turns_per_phase: int
    phase_connection: str
    coil_shape: str
    phase_assignment_by_coil: tuple[str, ...]
    coil_pitch_mechanical_deg: float
    coil_radial_clearance_m: float
    conductor_fill_factor: float
    analytical_projection_winding_factor: float

    def __post_init__(self) -> None:
        if self.total_coils != self.phases * self.coils_per_phase:
            raise ValueError("total_coils must equal phases * coils_per_phase")
        if len(self.phase_assignment_by_coil) != self.total_coils:
            raise ValueError("every physical coil requires an explicit phase assignment and polarity")
        if self.coils_per_phase != self.series_coils_per_branch * self.parallel_branches:
            raise ValueError("coils_per_phase must match the explicit branch network")
        expected_turns = self.turns_per_coil * self.series_coils_per_branch
        if self.effective_series_turns_per_phase != expected_turns:
            raise ValueError("effective series turns must follow the explicit winding network")
        if not 0.0 < self.conductor_fill_factor <= 1.0:
            raise ValueError("conductor_fill_factor must be within (0, 1]")
        if not 0.0 < self.analytical_projection_winding_factor <= 1.0:
            raise ValueError("analytical projection winding factor must be within (0, 1]")


@dataclass(frozen=True)
class FEAOperatingPoint:
    no_load_speed_rpm: float
    phase_current_rms_a: float
    rotor_angle_start_deg: float
    rotor_angle_end_deg: float
    rotor_angle_step_deg: float
    operating_temperature_c: float


@dataclass(frozen=True)
class FEABoundaryConditions:
    outer_boundary: str
    periodic_symmetry: str
    motion_method: str
    phase_current_condition: str
    magnetization_definition: str


@dataclass(frozen=True)
class FEAMeshLevel:
    name: str
    global_size_m: float
    air_gap_size_m: float
    magnet_edge_size_m: float
    winding_size_m: float


@dataclass(frozen=True)
class FEAMeshPlan:
    levels: tuple[FEAMeshLevel, ...]
    acceptance_tolerance_percent: float
    acceptance_rule: str

    def __post_init__(self) -> None:
        if len(self.levels) < 3:
            raise ValueError("mesh convergence requires at least coarse, medium, and fine levels")
        if self.acceptance_tolerance_percent <= 0.0:
            raise ValueError("mesh convergence tolerance must be positive")


@dataclass(frozen=True)
class FEAOutputDefinition:
    primary_metric: str
    required_signals: tuple[str, ...]
    waveform_period: str
    endpoint_policy: str
    extraction_notes: str


@dataclass(frozen=True)
class FEAReferenceProvenance:
    reference_label: str
    parameter_origin: str
    created_for_phase: str
    evidence_classification_after_acceptance: EvidenceClassification
    notes: tuple[str, ...]


@dataclass(frozen=True)
class FEAReferenceDefinition:
    reference_id: str
    execution_status: FEAExecutionStatus
    planned_solver: FEASolverMetadata
    geometry: FEAReferenceGeometry
    materials: FEAReferenceMaterials
    winding: FEAReferenceWinding
    operating_point: FEAOperatingPoint
    boundary_conditions: FEABoundaryConditions
    mesh_plan: FEAMeshPlan
    output: FEAOutputDefinition
    provenance: FEAReferenceProvenance


@dataclass(frozen=True)
class FEAMeshConvergencePoint:
    mesh_name: str
    element_count: int
    back_emf_phase_rms_v: float | None
    flux_linkage_peak_wb_turn: float | None
    torque_nm: float | None = None


@dataclass(frozen=True)
class FEAMeshConvergenceResult:
    accepted: bool
    tolerance_percent: float
    maximum_successive_change_percent: float
    changes_percent: Mapping[str, tuple[float, ...]]
    notes: tuple[str, ...]


@dataclass(frozen=True)
class FEAExecutionResult:
    status: FEAExecutionStatus
    solver_metadata: FEASolverMetadata
    result_path: Path | None
    warning_messages: tuple[str, ...]


class FEASolverAdapter(Protocol):
    def is_available(self) -> bool: ...

    def execute(self, reference: FEAReferenceDefinition) -> FEAExecutionResult: ...


def _positive_finite_fields(instance: Any, names: tuple[str, ...]) -> None:
    for name in names:
        value = getattr(instance, name)
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError(f"{name} must be finite and positive")


def _validate_reference(reference: FEAReferenceDefinition) -> None:
    _positive_finite_fields(
        reference.geometry,
        (
            "inner_radius_m", "outer_radius_m", "physical_air_gap_per_side_m",
            "magnet_thickness_m", "rotor_support_thickness_m", "winding_axial_thickness_m",
            "air_domain_radial_margin_m", "air_domain_axial_margin_m",
        ),
    )
    if reference.geometry.outer_radius_m <= reference.geometry.inner_radius_m:
        raise ValueError("outer radius must exceed inner radius")
    if not 0.0 < reference.geometry.magnet_arc_ratio <= 1.0:
        raise ValueError("magnet_arc_ratio must be within (0, 1]")
    if reference.provenance.reference_label != "CONTROLLED_FEA_REFERENCE":
        raise ValueError("Phase 7H controlled machine must retain its explicit label")
    if reference.provenance.evidence_classification_after_acceptance is not EvidenceClassification.INDEPENDENT_FEA_REFERENCE:
        raise ValueError("controlled solver output may only become independent FEA evidence")


def load_fea_reference_definition(path: Path) -> FEAReferenceDefinition:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    reference = FEAReferenceDefinition(
        reference_id=raw["reference_id"],
        execution_status=FEAExecutionStatus(raw["execution_status"]),
        planned_solver=FEASolverMetadata(
            solver=raw["solver"]["solver"],
            solver_version=raw["solver"]["solver_version"],
            model_version=raw["solver"]["model_version"],
            dimensionality=FEADimensionality(raw["solver"]["dimensionality"]),
            fidelity_tier=FEAFidelityTier(raw["solver"]["fidelity_tier"]),
            automation_path=raw["solver"]["automation_path"],
        ),
        geometry=FEAReferenceGeometry(**raw["geometry"]),
        materials=FEAReferenceMaterials(**raw["materials"]),
        winding=FEAReferenceWinding(
            **{
                **raw["winding"],
                "phase_assignment_by_coil": tuple(raw["winding"]["phase_assignment_by_coil"]),
            }
        ),
        operating_point=FEAOperatingPoint(**raw["operating_point"]),
        boundary_conditions=FEABoundaryConditions(**raw["boundary_conditions"]),
        mesh_plan=FEAMeshPlan(
            levels=tuple(FEAMeshLevel(**level) for level in raw["mesh_plan"]["levels"]),
            acceptance_tolerance_percent=raw["mesh_plan"]["acceptance_tolerance_percent"],
            acceptance_rule=raw["mesh_plan"]["acceptance_rule"],
        ),
        output=FEAOutputDefinition(
            primary_metric=raw["output"]["primary_metric"],
            required_signals=tuple(raw["output"]["required_signals"]),
            waveform_period=raw["output"]["waveform_period"],
            endpoint_policy=raw["output"]["endpoint_policy"],
            extraction_notes=raw["output"]["extraction_notes"],
        ),
        provenance=FEAReferenceProvenance(
            reference_label=raw["provenance"]["reference_label"],
            parameter_origin=raw["provenance"]["parameter_origin"],
            created_for_phase=raw["provenance"]["created_for_phase"],
            evidence_classification_after_acceptance=EvidenceClassification(
                raw["provenance"]["evidence_classification_after_acceptance"]
            ),
            notes=tuple(raw["provenance"]["notes"]),
        ),
    )
    _validate_reference(reference)
    return reference


def _relative_change_percent(previous: float, current: float) -> float:
    if current == 0.0:
        return 0.0 if previous == 0.0 else math.inf
    return abs(current - previous) / abs(current) * 100.0


def assess_mesh_convergence(
    points: tuple[FEAMeshConvergencePoint, ...],
    tolerance_percent: float,
) -> FEAMeshConvergenceResult:
    if len(points) < 3:
        raise ValueError("at least three mesh results are required")
    if tolerance_percent <= 0.0 or not math.isfinite(tolerance_percent):
        raise ValueError("tolerance_percent must be finite and positive")
    if any(right.element_count <= left.element_count for left, right in zip(points, points[1:])):
        raise ValueError("element counts must increase with each refinement")

    changes: dict[str, tuple[float, ...]] = {}
    for name in ("back_emf_phase_rms_v", "flux_linkage_peak_wb_turn", "torque_nm"):
        values = tuple(getattr(point, name) for point in points)
        if all(value is None for value in values):
            continue
        if any(value is None or not math.isfinite(value) for value in values):
            raise ValueError(f"{name} must be finite at every mesh level when tracked")
        changes[name] = tuple(
            _relative_change_percent(float(previous), float(current))
            for previous, current in zip(values, values[1:])
        )
    if not changes:
        raise ValueError("at least one convergence metric must be tracked")
    maximum = max(change for metric_changes in changes.values() for change in metric_changes)
    accepted = maximum <= tolerance_percent
    return FEAMeshConvergenceResult(
        accepted=accepted,
        tolerance_percent=tolerance_percent,
        maximum_successive_change_percent=maximum,
        changes_percent=MappingProxyType(changes),
        notes=(
            "Every coarse-to-medium and medium-to-fine change must satisfy the project tolerance.",
            "This is a project acceptance rule, not an industry-standard tolerance.",
        ),
    )
