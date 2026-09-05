"""Build a deterministic FEA validation case from a MotorCalculator design.

The builder is read-only with respect to the analytical model: it consumes a
``MotorAnalysisInput`` and an ``AnalysisResult`` and produces a case description.
It never writes back, never adjusts an analytical parameter, and never fills in
a physical quantity the schema does not contain.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..motor_core.electrical_semantics import MotorControlMode
from ..motor_core.models import AnalysisResult, MotorAnalysisInput
from ..version import APPLICATION_VERSION
from .geometry import (
    AIR_DOMAIN_MARGIN_POLE_PITCHES,
    OMITTED_THREE_DIMENSIONAL_EFFECTS,
    derive_symmetry_plan,
)
from .hashing import compute_case_hash
from .materials import build_material_set
from .models import (
    FEA_CASE_SCHEMA_VERSION,
    FEAAnalyticalPrediction,
    FEACoreModelPolicy,
    FEAMeshPolicy,
    FEAOperatingPoint,
    FEASupportability,
    FEASupportabilityReport,
    FEAUnrolledSliceGeometry,
    FEAValidationCase,
    FEAValidationTarget,
)
from .sampling import plan_angle_sampling
from .winding import build_winding_map

#: FEMM is a 2D solver, so a slice of an axial-flux machine can never be more
#: than a simplified magnetic reference. Phase 7H fixed this vocabulary.
FEA_FIDELITY_TIER = "FEA_TIER_3"

SOLVER_FAMILY = "FEMM_MAGNETOSTATIC_PLANAR"

UNITS = {
    "length": "meter",
    "angle": "mechanical_degree",
    "flux_density": "tesla",
    "flux_linkage": "weber_turn",
    "voltage": "volt",
    "current": "ampere_rms_per_phase",
    "force": "newton",
    "torque": "newton_meter",
    "speed": "revolution_per_minute_mechanical",
}

BACK_EMF_EXTRACTION_METHOD = (
    "magnetostatic solve at each rotor position; phase flux linkage read from the "
    "circuit property; back-EMF obtained as e = omega_mech * d(lambda)/d(theta_mech) "
    "by spectral differentiation of the periodic flux-linkage waveform"
)

TORQUE_EXTRACTION_METHOD = (
    "weighted Maxwell stress tensor force in the circumferential direction on the "
    "rotor blocks, converted to torque as T = F_x * r_mean; the planar model is a "
    "linear machine, so the conversion to a rotary quantity is explicit"
)

#: Approximation labels attached to every case this bridge can build.
BASE_APPROXIMATION_LABELS = (
    "MEAN_RADIUS_UNROLLED_2D_SLICE",
    "NO_END_WINDING_GEOMETRY",
    "NO_INNER_OUTER_EDGE_FRINGING",
    "MAGNETOSTATIC_NO_EDDY_REACTION",
)

CORED_APPROXIMATION_LABELS = (
    "CORED_AFPM_MAGNET_ARRANGEMENT_NOT_DECLARED_IN_SCHEMA",
    "ANALYTICAL_GAP_INCLUDES_COIL_HEIGHT_EVEN_WHEN_CORED",
)

CORELESS_COGGING_NOTE = (
    "a slotless stator has no cogging by construction, so the analytical cogging "
    "prediction is exactly zero and the FEA comparison measures the solver noise "
    "floor rather than a physical cogging amplitude"
)

COGGING_MODEL_PROVENANCE = (
    "ANALYTICAL_COGGING_IS_A_USER_SUPPLIED_RATIO: the analytical peak is "
    "k_cogging_peak * rated_torque with k_cogging_peak derived from the entered "
    "cogging factor, not from a field solution; the comparison therefore tests "
    "the entered assumption, not a physics formula"
)


@dataclass(frozen=True)
class FEAModellingParameters:
    """FEA-only modelling values that the MotorCalculator schema does not carry.

    These must be supplied explicitly. There is no silent default: a case built
    without them is reported as ``NOT_ENOUGH_GEOMETRY`` instead of being
    quietly completed with an invented number.
    """

    rotor_back_iron_thickness_m: float
    coil_span_slots: int
    provenance: str
    core_model_policy: FEACoreModelPolicy | None = None
    core_library_material_name: str | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.rotor_back_iron_thickness_m) or self.rotor_back_iron_thickness_m <= 0.0:
            raise ValueError("rotor_back_iron_thickness_m must be finite and positive")
        if self.coil_span_slots <= 0:
            raise ValueError("coil_span_slots must be a positive number of slots")
        if not self.provenance.strip():
            raise ValueError("modelling parameters require an explicit provenance statement")


def assess_supportability(
    inputs: MotorAnalysisInput,
    *,
    modelling: FEAModellingParameters | None,
) -> FEASupportabilityReport:
    """Decide whether this design can be mapped onto the FEMM bridge."""

    topology = (
        "axial_flux_single_stator_dual_rotor_coreless"
        if inputs.is_coreless
        else "axial_flux_single_stator_dual_rotor_cored"
    )
    dimensionality_note = (
        "planar 2D mean-radius unrolled slice of a 3D axial-flux machine"
    )
    blocking: list[str] = []
    labels = list(BASE_APPROXIMATION_LABELS)

    if modelling is None:
        blocking.append(
            "rotor back-iron thickness and coil span are not part of the "
            "MotorCalculator schema and were not supplied as explicit FEA "
            "modelling parameters"
        )
        return FEASupportabilityReport(
            state=FEASupportability.NOT_ENOUGH_GEOMETRY,
            topology=topology,
            dimensionality_note=dimensionality_note,
            fidelity_tier=FEA_FIDELITY_TIER,
            blocking_reasons=tuple(blocking),
            approximation_labels=tuple(labels),
        )

    if modelling.coil_span_slots >= inputs.slot_count:
        blocking.append(
            f"the declared coil span of {modelling.coil_span_slots} slots is not less "
            f"than the slot count Q={inputs.slot_count}"
        )
    if inputs.slot_count % 3 != 0:
        blocking.append(
            f"Q={inputs.slot_count} is not divisible by the three phases, so no "
            "balanced phase circuit assignment exists"
        )
    if inputs.outer_diameter_m <= inputs.inner_diameter_m:
        blocking.append("outer diameter must exceed inner diameter")
    if inputs.magnet_width_m <= 0.0 or inputs.magnet_thickness_m <= 0.0:
        blocking.append("magnet width and thickness must be positive")

    if blocking:
        return FEASupportabilityReport(
            state=FEASupportability.NOT_ENOUGH_GEOMETRY
            if any("schema" in reason or "diameter" in reason for reason in blocking)
            else FEASupportability.UNSUPPORTED,
            topology=topology,
            dimensionality_note=dimensionality_note,
            fidelity_tier=FEA_FIDELITY_TIER,
            blocking_reasons=tuple(blocking),
            approximation_labels=tuple(labels),
        )

    if inputs.is_coreless:
        # The coreless dual-rotor machine is the one arrangement whose analytical
        # magnetic circuit maps onto exactly one physical geometry, so it is the
        # only fully supported case.
        return FEASupportabilityReport(
            state=FEASupportability.SUPPORTED,
            topology=topology,
            dimensionality_note=dimensionality_note,
            fidelity_tier=FEA_FIDELITY_TIER,
            blocking_reasons=(),
            approximation_labels=tuple(labels),
        )

    labels.extend(CORED_APPROXIMATION_LABELS)
    return FEASupportabilityReport(
        state=FEASupportability.PARTIALLY_SUPPORTED,
        topology=topology,
        dimensionality_note=dimensionality_note,
        fidelity_tier=FEA_FIDELITY_TIER,
        blocking_reasons=(),
        approximation_labels=tuple(labels),
    )


def build_slice_geometry(
    inputs: MotorAnalysisInput, modelling: FEAModellingParameters
) -> FEAUnrolledSliceGeometry:
    """Map the annular machine onto its mean-radius unrolled slice."""

    mean_diameter = (inputs.outer_diameter_m + inputs.inner_diameter_m) / 2.0
    mean_radius = mean_diameter / 2.0
    radial_length = (inputs.outer_diameter_m - inputs.inner_diameter_m) / 2.0
    circumference = math.pi * mean_diameter
    pole_pitch = circumference / float(2 * inputs.pole_pairs)
    slot_pitch = circumference / float(inputs.slot_count)
    # The magnet spans the pole-arc fraction of the pole pitch, which is the same
    # coverage the analytical pole area applies.
    magnet_arc = pole_pitch * inputs.pole_arc_coefficient

    cored = not inputs.is_coreless
    return FEAUnrolledSliceGeometry(
        mean_radius_m=mean_radius,
        radial_active_length_m=radial_length,
        circumference_m=circumference,
        pole_pairs=inputs.pole_pairs,
        slot_count=inputs.slot_count,
        pole_pitch_m=pole_pitch,
        slot_pitch_m=slot_pitch,
        magnet_thickness_m=inputs.magnet_thickness_m,
        magnet_arc_length_m=magnet_arc,
        pole_arc_coefficient=inputs.pole_arc_coefficient,
        mechanical_air_gap_per_side_m=inputs.air_gap_per_side_m,
        winding_region_thickness_m=inputs.coil_height_m,
        rotor_back_iron_thickness_m=modelling.rotor_back_iron_thickness_m,
        is_coreless=inputs.is_coreless,
        stator_core_thickness_m=inputs.stator_thickness_m if cored else None,
        slot_height_m=inputs.slot_height_m if cored else None,
        slot_top_width_m=inputs.slot_top_width_m,
        slot_bottom_width_m=inputs.slot_bottom_width_m,
        slot_opening_height_m=inputs.slot_opening_height_m if cored else None,
        slot_opening_width_m=inputs.slot_opening_width_m if cored else None,
        wedge_height_m=inputs.wedge_height_m if cored else None,
        yoke_height_m=inputs.yoke_height_m if cored else None,
        air_domain_margin_m=pole_pitch * AIR_DOMAIN_MARGIN_POLE_PITCHES,
        omitted_three_dimensional_effects=OMITTED_THREE_DIMENSIONAL_EFFECTS,
    )


def build_mesh_policy(geometry: FEAUnrolledSliceGeometry) -> FEAMeshPolicy:
    """Size the mesh from the physics, not from a fixed element budget.

    The air gap governs every validated quantity, so it is meshed to a fraction
    of the gap itself. Magnet edges set the harmonic content of the flux
    waveform. The far air domain is deliberately coarse.
    """

    gap = geometry.mechanical_air_gap_per_side_m
    pole_pitch = geometry.pole_pitch_m
    air_gap_size = gap / 3.0
    global_size = pole_pitch / 12.0
    if air_gap_size >= global_size:
        # A very large mechanical gap relative to the pole pitch would otherwise
        # make the "fine" gap mesh coarser than the global default.
        global_size = air_gap_size * 4.0
    return FEAMeshPolicy(
        name="phase10a_default",
        global_size_m=global_size,
        air_gap_size_m=air_gap_size,
        magnet_size_m=min(geometry.magnet_thickness_m / 4.0, pole_pitch / 12.0),
        magnet_edge_size_m=min(geometry.magnet_thickness_m / 8.0, pole_pitch / 24.0),
        slot_opening_size_m=(
            None
            if geometry.is_coreless
            else max(float(geometry.slot_opening_width_m or 0.0) / 4.0, air_gap_size / 2.0)
        ),
        winding_size_m=geometry.winding_region_thickness_m / 4.0,
        core_size_m=None if geometry.is_coreless else pole_pitch / 10.0,
        air_domain_size_m=global_size * 6.0,
        minimum_angle_deg=30.0,
        convergence_claim="NO_CONVERGENCE_CLAIM_SINGLE_MESH",
    )


def _capture_analytical(
    inputs: MotorAnalysisInput, analysis: AnalysisResult
) -> FEAAnalyticalPrediction:
    electrical = analysis.electrical
    performance = analysis.performance
    magnetic = analysis.magnetic
    return FEAAnalyticalPrediction(
        back_emf_phase_rms_v=electrical.back_emf_phase_rms_v,
        back_emf_line_rms_v=electrical.back_emf_line_rms_v,
        back_emf_constant_phase_rms_v_per_rad_s=electrical.back_emf_constant_phase_rms_v_per_rad_s,
        flux_per_pole_wb=magnetic.pole_flux_wb,
        air_gap_flux_density_peak_t=magnetic.air_gap_flux_density_peak_t,
        average_torque_nm=performance.average_torque_nm,
        torque_constant_nm_per_phase_rms_a=electrical.torque_constant_nm_per_phase_rms_a,
        cogging_torque_peak_nm=performance.cogging_torque_peak_nm,
        cogging_model_provenance=COGGING_MODEL_PROVENANCE,
        basis_notes={
            "back_emf": "phase RMS and line RMS of the fundamental sinusoidal model",
            "current": "phase RMS",
            "torque": "shaft-equivalent average electromagnetic torque, newton metre",
            "speed": "mechanical rpm; electrical frequency is p times mechanical",
            "angle": "mechanical degrees; electrical angle is p times mechanical",
        },
    )


def build_validation_case(
    inputs: MotorAnalysisInput,
    analysis: AnalysisResult,
    *,
    target: FEAValidationTarget,
    modelling: FEAModellingParameters | None,
    winding_factor_provenance: str = "analytical_input_winding_factor",
    apply_symmetry: bool = False,
) -> FEAValidationCase:
    """Build one deterministic FEA validation case.

    Raises when the design cannot be mapped; the caller should call
    :func:`assess_supportability` first if it wants the reason without an
    exception.
    """

    supportability = assess_supportability(inputs, modelling=modelling)
    if supportability.state in (
        FEASupportability.UNSUPPORTED,
        FEASupportability.NOT_ENOUGH_GEOMETRY,
    ):
        raise ValueError(
            "this design cannot be mapped to the FEMM bridge: "
            + "; ".join(supportability.blocking_reasons)
        )
    assert modelling is not None  # guaranteed by the supportability gate above

    geometry = build_slice_geometry(inputs, modelling)
    materials = build_material_set(
        remanence_t=inputs.remanence_t,
        magnet_relative_permeability=inputs.magnet_relative_permeability,
        coil_temperature_c=inputs.coil_temperature_c,
        is_coreless=inputs.is_coreless,
        core_model_policy=modelling.core_model_policy,
        core_library_material_name=modelling.core_library_material_name,
    )
    winding = build_winding_map(
        slots=inputs.slot_count,
        pole_pairs=inputs.pole_pairs,
        turns_per_phase=inputs.turns_per_phase,
        parallel_paths=inputs.parallel_paths,
        coil_span_slots=modelling.coil_span_slots,
        winding_factor_analytical=inputs.winding_factor,
        winding_factor_provenance=winding_factor_provenance,
        wire_diameter_m=inputs.wire_diameter_m,
    )
    sampling = plan_angle_sampling(
        target=target, slot_count=inputs.slot_count, pole_pairs=inputs.pole_pairs
    )
    symmetry = derive_symmetry_plan(
        slot_count=inputs.slot_count,
        pole_count=2 * inputs.pole_pairs,
        target=target,
        apply_symmetry=apply_symmetry,
    )
    mesh_policy = build_mesh_policy(geometry)

    excitation_current = (
        analysis.performance.phase_current_rms_a
        if target is FEAValidationTarget.AVERAGE_TORQUE
        else 0.0
    )
    operating_point = FEAOperatingPoint(
        target=target,
        mechanical_speed_rpm=inputs.mechanical_speed_rpm,
        phase_current_rms_a=excitation_current,
        # id = 0 control: the current vector leads the rotor flux by 90
        # electrical degrees, which is the same operating assumption the
        # analytical torque constant is defined at.
        current_angle_electrical_deg=90.0 if excitation_current > 0.0 else 0.0,
        temperature_c=inputs.coil_temperature_c,
        rotor_angle_start_mech_deg=0.0,
        rotor_angle_span_mech_deg=sampling.span_mech_deg,
        rotor_angle_sample_count=sampling.sample_count,
        sampling_rationale=sampling.rationale,
    )

    notes: list[str] = [
        modelling.provenance,
        (
            f"coil span is a declared FEA modelling parameter: {modelling.coil_span_slots} "
            f"slot(s) against a full pitch of {inputs.slot_count / (2 * inputs.pole_pairs):.4f} "
            "slots; the MotorCalculator schema does not carry a coil span"
        ),
    ]
    if inputs.is_coreless and target is FEAValidationTarget.COGGING_TORQUE:
        notes.append(CORELESS_COGGING_NOTE)
    if inputs.control_mode is not MotorControlMode.PMSM_SINUSOIDAL:
        notes.append(
            "the analytical back-EMF for this design uses the trapezoidal BLDC "
            "factor, whose waveform semantics remain provisional; the FEA "
            "comparison is against that provisional analytical value"
        )

    case = FEAValidationCase(
        case_id="",
        schema_version=FEA_CASE_SCHEMA_VERSION,
        application_version=APPLICATION_VERSION,
        target=target,
        supportability=supportability,
        geometry=geometry,
        materials=materials,
        winding=winding,
        operating_point=operating_point,
        mesh_policy=mesh_policy,
        symmetry=symmetry,
        analytical=_capture_analytical(inputs, analysis),
        units=UNITS,
        solver_family=SOLVER_FAMILY,
        torque_extraction_method=TORQUE_EXTRACTION_METHOD,
        back_emf_extraction_method=BACK_EMF_EXTRACTION_METHOD,
        notes=tuple(notes),
    )
    from dataclasses import replace

    return replace(case, case_id=compute_case_hash(case))
