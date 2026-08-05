"""Opt-in midpoint radial integration for sinusoidal AFPM back-EMF."""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType

from .electrical import AFPMInductance, BackEMFScope, BackEMFSemantics, BackEMFValueKind, WaveformFamily
from .geometry import AFPMGeometry, RadialMagnetSample
from .source_adapter import AdvancedAFPMCase
from .topology import AFPMTopology, AFPMTopologyType
from .torque_semantics import TorqueBoundary, TorqueSemantics
from .winding import AFPMWinding, WindingType


class RadialSliceInputError(ValueError):
    def __init__(self, missing_fields: tuple[str, ...]):
        self.missing_fields = missing_fields
        super().__init__(f"radial-slice inputs unavailable: {', '.join(missing_fields)}")


@dataclass(frozen=True)
class RadialSliceContribution:
    radius_m: float
    magnet_coverage: float
    active_pole_area_m2: float
    flux_wb: float


@dataclass(frozen=True)
class RadialSliceBackEMFResult:
    slice_count: int
    integration_method: str
    air_gap_flux_density_t: float
    pole_flux_wb: float
    electrical_frequency_hz: float
    phase_fundamental_rms_v: float
    voltage_aggregation_multiplier: float
    contributions: tuple[RadialSliceContribution, ...]
    assumptions: tuple[str, ...]


@dataclass(frozen=True)
class MeanRadiusBackEMFResult:
    phase_fundamental_rms_v: float
    pole_flux_wb: float
    mean_radius_m: float
    magnet_coverage_at_mean_radius: float


@dataclass(frozen=True)
class ConvergencePoint:
    slice_count: int
    phase_fundamental_rms_v: float
    relative_difference_from_previous_percent: float | None


def _missing_solver_fields(case: AdvancedAFPMCase) -> tuple[str, ...]:
    geometry = case.geometry
    checks = {
        "geometry.inner_radius_m": geometry.inner_radius_m is not None,
        "geometry.outer_radius_m": geometry.outer_radius_m is not None,
        "geometry.effective_nonmagnetic_gap_m": geometry.effective_nonmagnetic_gap_m is not None,
        "geometry.magnet_thickness_m": geometry.magnet_thickness_m is not None,
        "geometry.pole_pairs": geometry.pole_pairs is not None,
        "geometry.magnet_coverage": geometry.magnet_arc_ratio is not None or bool(geometry.radius_dependent_magnet_profile),
        "material.remanence_t": case.remanence_t is not None,
        "material.magnet_relative_permeability": case.magnet_relative_permeability is not None,
        "winding.turns_per_phase": case.winding.turns_per_phase is not None,
        "winding.winding_factor": case.winding.winding_factor is not None,
        "back_emf.speed_rpm": case.back_emf_semantics is not None,
        "topology": case.topology.topology_type is not AFPMTopologyType.UNKNOWN,
    }
    if case.topology.topology_type is AFPMTopologyType.DSSR:
        interconnection = (case.winding.stator_interconnection or "").lower()
        checks["winding.stator_interconnection"] = "parallel" in interconnection or "series" in interconnection
    return tuple(name for name, present in checks.items() if not present)


def _topology_factors(case: AdvancedAFPMCase) -> tuple[int, float]:
    topology_type = case.topology.topology_type
    if topology_type is AFPMTopologyType.SSDR:
        return 2, 1.0
    if topology_type is AFPMTopologyType.SINGLE_SIDED:
        return 1, 1.0
    if topology_type is AFPMTopologyType.DSSR:
        interconnection = (case.winding.stator_interconnection or "").lower()
        if "parallel" in interconnection:
            return 1, 1.0
        if "series" in interconnection:
            return 1, float(case.topology.stator_count)
    raise RadialSliceInputError(("topology_flux_path_or_stator_interconnection",))


def _air_gap_flux_density(case: AdvancedAFPMCase, magnet_layers: int) -> float:
    geometry = case.geometry
    total_magnet_length = magnet_layers * float(geometry.magnet_thickness_m)
    return float(case.remanence_t) * total_magnet_length / (
        total_magnet_length
        + float(case.magnet_relative_permeability) * float(geometry.effective_nonmagnetic_gap_m)
    )


class RadialSliceBackEMFModel:
    """Compute phase fundamental RMS voltage without production dependencies."""

    def compute(self, case: AdvancedAFPMCase, *, slice_count: int = 100) -> RadialSliceBackEMFResult:
        if not isinstance(slice_count, int) or slice_count <= 0:
            raise ValueError("slice_count must be a positive integer")
        missing = _missing_solver_fields(case)
        if missing:
            raise RadialSliceInputError(missing)
        geometry = case.geometry
        inner = float(geometry.inner_radius_m)
        outer = float(geometry.outer_radius_m)
        pole_pairs = int(geometry.pole_pairs)
        dr = (outer - inner) / slice_count
        pole_sector_angle_rad = math.pi / pole_pairs
        magnet_layers, voltage_multiplier = _topology_factors(case)
        flux_density = _air_gap_flux_density(case, magnet_layers)
        contributions = []
        pole_flux = 0.0
        for index in range(slice_count):
            radius = inner + (index + 0.5) * dr
            coverage = geometry.magnet_coverage_at(radius)
            active_pole_area = pole_sector_angle_rad * radius * dr * coverage
            local_flux = flux_density * active_pole_area
            pole_flux += local_flux
            contributions.append(RadialSliceContribution(radius, coverage, active_pole_area, local_flux))
        speed_rpm = float(case.back_emf_semantics.speed_rpm)
        frequency_hz = pole_pairs * speed_rpm / 60.0
        phase_rms = (
            4.44
            * frequency_hz
            * int(case.winding.turns_per_phase)
            * float(case.winding.winding_factor)
            * pole_flux
            * voltage_multiplier
        )
        return RadialSliceBackEMFResult(
            slice_count=slice_count,
            integration_method="midpoint",
            air_gap_flux_density_t=flux_density,
            pole_flux_wb=pole_flux,
            electrical_frequency_hz=frequency_hz,
            phase_fundamental_rms_v=phase_rms,
            voltage_aggregation_multiplier=voltage_multiplier,
            contributions=tuple(contributions),
            assumptions=(
                "Linear recoil magnetic circuit: B = Br*lm_total/(lm_total + mur*g_effective).",
                "No leakage, fringing, saturation, slotting, or empirical correction coefficient.",
                "Local pole area is (pi/p)*r*dr*local_magnet_arc_ratio.",
                "Voltage is sinusoidal phase fundamental RMS using 4.44*f*N*Phi*kw.",
                "DSSR parallel stators preserve per-stator voltage; series stators sum voltage.",
            ),
        )

    def compute_mean_radius(self, case: AdvancedAFPMCase) -> MeanRadiusBackEMFResult:
        missing = _missing_solver_fields(case)
        if missing:
            raise RadialSliceInputError(missing)
        geometry = case.geometry
        inner = float(geometry.inner_radius_m)
        outer = float(geometry.outer_radius_m)
        pole_pairs = int(geometry.pole_pairs)
        mean_radius = 0.5 * (inner + outer)
        coverage = geometry.magnet_coverage_at(mean_radius)
        magnet_layers, voltage_multiplier = _topology_factors(case)
        flux_density = _air_gap_flux_density(case, magnet_layers)
        full_pole_sector_area = math.pi * (outer**2 - inner**2) / (2.0 * pole_pairs)
        pole_flux = flux_density * full_pole_sector_area * coverage
        frequency_hz = pole_pairs * float(case.back_emf_semantics.speed_rpm) / 60.0
        phase_rms = (
            4.44
            * frequency_hz
            * int(case.winding.turns_per_phase)
            * float(case.winding.winding_factor)
            * pole_flux
            * voltage_multiplier
        )
        return MeanRadiusBackEMFResult(phase_rms, pole_flux, mean_radius, coverage)


def convergence_study(
    case: AdvancedAFPMCase,
    slice_counts: tuple[int, ...] = (10, 50, 100, 500),
) -> tuple[ConvergencePoint, ...]:
    model = RadialSliceBackEMFModel()
    points = []
    previous = None
    for count in slice_counts:
        value = model.compute(case, slice_count=count).phase_fundamental_rms_v
        relative = None if previous is None else abs(value - previous) / abs(value) * 100.0
        points.append(ConvergencePoint(count, value, relative))
        previous = value
    return tuple(points)


def build_synthetic_radial_reference_case() -> AdvancedAFPMCase:
    """Return a documented analytical sandbox case, never external evidence."""
    topology = AFPMTopology(
        AFPMTopologyType.SSDR, 1, 2, 2,
        "central stator winding", "inward faces of both rotors",
    )
    geometry = AFPMGeometry(
        inner_radius_m=0.05,
        outer_radius_m=0.10,
        air_gap_m=0.001,
        magnet_thickness_m=0.005,
        pole_pairs=5,
        magnet_arc_ratio=None,
        radius_dependent_magnet_profile=(
            RadialMagnetSample(0.05, 0.45),
            RadialMagnetSample(0.075, 0.65),
            RadialMagnetSample(0.10, 0.80),
        ),
        stator_count=1,
        rotor_count=2,
        effective_nonmagnetic_gap_m=0.012,
    )
    winding = AFPMWinding(
        turns_per_coil=None,
        coils_per_phase=None,
        turns_per_phase=100,
        parallel_branches=1,
        connection="Y",
        winding_factor=0.95,
        pitch_factor=None,
        distribution_factor=None,
        winding_type=WindingType.DISTRIBUTED,
    )
    return AdvancedAFPMCase(
        case_id="synthetic_radial_integration_reference",
        source_id="synthetic_internal_only",
        source_title="Synthetic radial integration reference",
        source_url="internal://phase7e",
        topology=topology,
        geometry=geometry,
        winding=winding,
        back_emf_semantics=BackEMFSemantics(
            BackEMFScope.PHASE,
            BackEMFValueKind.FUNDAMENTAL_RMS,
            WaveformFamily.SINUSOIDAL,
            1000.0,
            source_native_unit="V phase fundamental RMS",
        ),
        inductance=AFPMInductance(),
        torque_semantics=TorqueSemantics(TorqueBoundary.UNKNOWN),
        remanence_t=1.2,
        magnet_relative_permeability=1.05,
        back_emf_reference_field=None,
        source_fields=MappingProxyType({}),
        field_lineage=MappingProxyType({}),
        adapter_notes=("Synthetic analytical case; not external accuracy evidence.",),
    )
