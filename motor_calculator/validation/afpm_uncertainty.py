"""Opt-in uncertainty adapter for the frozen controlled AFPM reference machine."""

from __future__ import annotations

import math
from types import MappingProxyType
from typing import Mapping

from motor_calculator.advanced_afpm.electrical import (
    AFPMInductance,
    BackEMFScope,
    BackEMFSemantics,
    BackEMFValueKind,
    WaveformFamily,
)
from motor_calculator.advanced_afpm.geometry import AFPMGeometry
from motor_calculator.advanced_afpm.radial_slice_back_emf import RadialSliceBackEMFModel
from motor_calculator.advanced_afpm.source_adapter import AdvancedAFPMCase
from motor_calculator.advanced_afpm.topology import AFPMTopology, AFPMTopologyType
from motor_calculator.advanced_afpm.torque_semantics import TorqueBoundary, TorqueSemantics
from motor_calculator.advanced_afpm.winding import AFPMWinding, WindingType
from motor_calculator.advanced_afpm.winding_network import (
    AFPMWindingNetwork,
    PhaseConnection,
    StatorConnection,
)

from .fea_reference import FEAReferenceDefinition


AFPM_BACK_EMF_PARAMETER_NAMES = (
    "magnet_remanence_t",
    "air_gap_m",
    "magnet_thickness_m",
    "winding_factor",
    "turns_per_phase",
    "inner_radius_m",
    "outer_radius_m",
    "magnet_arc_ratio",
    "magnet_relative_permeability",
)


def validate_physical_parameter_values(values: Mapping[str, float]) -> str | None:
    positive_names = (
        "magnet_remanence_t",
        "air_gap_m",
        "magnet_thickness_m",
        "turns_per_phase",
        "inner_radius_m",
        "outer_radius_m",
        "magnet_relative_permeability",
        "phase_resistance_ohm",
        "inertia_kg_m2",
    )
    for name in positive_names:
        if name in values and (not math.isfinite(values[name]) or values[name] <= 0.0):
            return f"{name}:must_be_finite_and_positive"
    nonnegative_names = (
        "viscous_damping_nm_per_rad_s",
        "load_torque_nm",
        "copper_temperature_coefficient_per_c",
    )
    for name in nonnegative_names:
        if name in values and (not math.isfinite(values[name]) or values[name] < 0.0):
            return f"{name}:must_be_finite_and_nonnegative"
    if "temperature_c" in values and not math.isfinite(values["temperature_c"]):
        return "temperature_c:must_be_finite"
    if "inner_radius_m" in values and "outer_radius_m" in values:
        if values["inner_radius_m"] >= values["outer_radius_m"]:
            return "geometry:inner_radius_m_must_be_less_than_outer_radius_m"
    if "winding_factor" in values and not 0.0 < values["winding_factor"] <= 1.0:
        return "winding_factor:must_be_within_0_and_1"
    if "magnet_arc_ratio" in values and not 0.0 < values["magnet_arc_ratio"] <= 1.0:
        return "magnet_arc_ratio:must_be_within_0_and_1"
    if "turns_per_phase" in values and not math.isclose(values["turns_per_phase"], round(values["turns_per_phase"])):
        return "turns_per_phase:must_be_an_integer"
    return None


def controlled_reference_nominal_values(reference: FEAReferenceDefinition) -> dict[str, float]:
    return {
        "magnet_remanence_t": reference.materials.magnet_remanence_t,
        "air_gap_m": reference.geometry.physical_air_gap_per_side_m,
        "magnet_thickness_m": reference.geometry.magnet_thickness_m,
        "winding_factor": reference.winding.analytical_projection_winding_factor,
        "turns_per_phase": float(reference.winding.effective_series_turns_per_phase),
        "inner_radius_m": reference.geometry.inner_radius_m,
        "outer_radius_m": reference.geometry.outer_radius_m,
        "magnet_arc_ratio": reference.geometry.magnet_arc_ratio,
        "magnet_relative_permeability": reference.materials.magnet_relative_permeability,
    }


def build_controlled_afpm_case(
    reference: FEAReferenceDefinition,
    parameter_values: Mapping[str, float],
) -> AdvancedAFPMCase:
    values = controlled_reference_nominal_values(reference)
    values.update(parameter_values)
    rejection = validate_physical_parameter_values(values)
    if rejection is not None:
        raise ValueError(rejection)
    turns_per_phase = int(round(values["turns_per_phase"]))
    series_coils = reference.winding.series_coils_per_branch
    if turns_per_phase % series_coils != 0:
        raise ValueError("turns_per_phase must divide evenly across frozen series coils")
    turns_per_coil = turns_per_phase // series_coils
    effective_nonmagnetic_gap = (
        reference.geometry.winding_axial_thickness_m + 2.0 * values["air_gap_m"]
    )
    topology = AFPMTopology(
        AFPMTopologyType.SSDR,
        reference.geometry.stator_count,
        reference.geometry.rotor_count,
        reference.geometry.active_air_gap_count,
        "central coreless stator winding",
        "inward faces of both rotors",
    )
    geometry = AFPMGeometry(
        inner_radius_m=values["inner_radius_m"],
        outer_radius_m=values["outer_radius_m"],
        air_gap_m=values["air_gap_m"],
        magnet_thickness_m=values["magnet_thickness_m"],
        pole_pairs=reference.geometry.pole_pairs,
        magnet_arc_ratio=values["magnet_arc_ratio"],
        radius_dependent_magnet_profile=None,
        stator_count=reference.geometry.stator_count,
        rotor_count=reference.geometry.rotor_count,
        effective_nonmagnetic_gap_m=effective_nonmagnetic_gap,
    )
    network = AFPMWindingNetwork(
        turns_per_coil=turns_per_coil,
        coils_per_phase=reference.winding.coils_per_phase,
        series_coils_per_branch=series_coils,
        parallel_branches=reference.winding.parallel_branches,
        number_of_stators=reference.geometry.stator_count,
        stator_connection=StatorConnection.INDEPENDENT,
        phase_connection=PhaseConnection.Y,
        winding_type=WindingType.CONCENTRATED,
        winding_factor=values["winding_factor"],
        pitch_factor=None,
        distribution_factor=None,
        winding_type_description=reference.winding.coil_shape,
    )
    return AdvancedAFPMCase(
        case_id=f"{reference.reference_id}_uncertainty_copy",
        source_id=reference.reference_id,
        source_title="Phase 7H controlled SSDR uncertainty projection",
        source_url="internal://phase7h-controlled-reference",
        topology=topology,
        geometry=geometry,
        winding=AFPMWinding(
            turns_per_coil=turns_per_coil,
            coils_per_phase=reference.winding.coils_per_phase,
            turns_per_phase=turns_per_phase,
            parallel_branches=reference.winding.parallel_branches,
            connection=reference.winding.phase_connection,
            winding_factor=values["winding_factor"],
            pitch_factor=None,
            distribution_factor=None,
            winding_type=WindingType.CONCENTRATED,
        ),
        winding_network=network,
        back_emf_semantics=BackEMFSemantics(
            BackEMFScope.PHASE,
            BackEMFValueKind.FUNDAMENTAL_RMS,
            WaveformFamily.SINUSOIDAL,
            reference.operating_point.no_load_speed_rpm,
            temperature_c=reference.operating_point.operating_temperature_c,
            source_native_unit="V phase fundamental RMS",
        ),
        inductance=AFPMInductance(),
        torque_semantics=TorqueSemantics(TorqueBoundary.UNKNOWN),
        remanence_t=values["magnet_remanence_t"],
        magnet_relative_permeability=values["magnet_relative_permeability"],
        back_emf_reference_field=None,
        source_fields=MappingProxyType({}),
        recovered_fields=MappingProxyType({}),
        field_lineage=MappingProxyType({}),
        adapter_notes=(
            "Fresh immutable case built from the frozen controlled reference and temporary uncertainty values.",
            "No uncertainty value is written back to the reference definition or production model.",
        ),
    )


def evaluate_controlled_back_emf_phase_rms_v(
    reference: FEAReferenceDefinition,
    parameter_values: Mapping[str, float],
    *,
    slice_count: int = 100,
) -> float:
    case = build_controlled_afpm_case(reference, parameter_values)
    return RadialSliceBackEMFModel().compute(case, slice_count=slice_count).phase_fundamental_rms_v


def numerical_integration_uncertainty_percent(
    reference: FEAReferenceDefinition,
    parameter_values: Mapping[str, float],
    slice_counts: tuple[int, ...] = (10, 50, 100, 500),
) -> float:
    if len(slice_counts) < 2:
        raise ValueError("numerical uncertainty requires at least two slice counts")
    values = tuple(
        evaluate_controlled_back_emf_phase_rms_v(
            reference, parameter_values, slice_count=slice_count
        )
        for slice_count in slice_counts
    )
    finest = values[-1]
    if finest == 0.0:
        return 0.0 if values[-2] == 0.0 else math.inf
    return abs(finest - values[-2]) / abs(finest) * 100.0
