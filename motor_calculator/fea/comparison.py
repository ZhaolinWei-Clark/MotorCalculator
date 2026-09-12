"""Analytical vs FEA comparison metrics, classification and attribution.

Three rules govern this module:

1. It never decides PASS or FAIL. The classification bands are descriptive and
   explicitly provisional.
2. It never divides by an effectively zero denominator; it says so instead.
3. It never changes an analytical parameter. Calibration is proposal-only, and
   :data:`AUTO_CALIBRATION_ENABLED` is a hard ``False``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from .models import FEAComparisonStatus, FEAValidationCase, FEAValidationTarget
from .results import (
    FEABackEmfExtraction,
    FEACoggingExtraction,
    FEARawResult,
    FEATorqueExtraction,
    extract_average_torque,
    extract_back_emf,
    extract_cogging,
)

FEA_COMPARISON_SCHEMA_VERSION = "phase10a.fea.comparison.v1"

#: Phase 10A never lets an FEA result modify an analytical parameter. This is a
#: constant, not a setting: there is no code path that flips it.
AUTO_CALIBRATION_ENABLED = False

#: Provisional, project-local agreement bands in percent. They are *not* an
#: industry standard and not an acceptance criterion; they exist so a reader can
#: sort many comparisons at a glance.
PROVISIONAL_CLOSE_AGREEMENT_PERCENT = 5.0
PROVISIONAL_MODERATE_DEVIATION_PERCENT = 20.0

PROVISIONAL_BAND_STATEMENT = (
    "PROVISIONAL_PROJECT_BANDS: close <= 5 percent, moderate <= 20 percent, "
    "large above 20 percent. These bands are a reading aid chosen by this "
    "project; they are not an industry tolerance and not a pass/fail criterion."
)

#: A denominator smaller than this fraction of the reference scale is treated as
#: effectively zero, and no relative error is reported against it.
DEGENERATE_DENOMINATOR_FRACTION = 1.0e-9

#: Plausible causes of disagreement. These are candidates offered for a human to
#: investigate; nothing here is an established cause for any particular case.
DISCREPANCY_CANDIDATES = {
    FEAValidationTarget.NO_LOAD_BACK_EMF: (
        "lumped magnetic-circuit simplification: one reluctance path per pole with no resolved field spreading",
        "the analytical `leakage_factor` is a scalar fitted stand-in for geometric inter-pole leakage",
        "the analytical Carter factor is a slot-type table value and ignores the entered slot opening width",
        "the analytical winding factor is a fundamental-only sinusoidal projection; the solver sees the full waveform",
        "2D mean-radius slice: no inner/outer edge fringing and no radial variation of pole pitch",
        "the FEA core permeability is a declared modelling parameter with no analytical counterpart",
        "mesh discretisation of the air gap and magnet edges",
    ),
    FEAValidationTarget.AVERAGE_TORQUE: (
        "the analytical torque follows from the rated-power specification and the torque constant, not from a field integral",
        "current-angle assumption: the comparison is defined at id = 0 and any other control angle is not comparable",
        "armature reaction and local saturation are absent from the analytical magnetic circuit",
        "2D mean-radius slice: end-winding contributes no torque and edge effects are absent",
        "the linear-to-rotary conversion T = F_x * r_mean uses the mean radius only",
        "mesh discretisation of the air gap where the stress tensor is evaluated",
    ),
    FEAValidationTarget.COGGING_TORQUE: (
        "the analytical cogging peak is a user-supplied ratio of rated torque, not a computed field quantity",
        "real cogging depends on slot opening width, magnet edge shape and skew, none of which enter the analytical ratio",
        "2D mean-radius slice: no radial variation of the slot/magnet overlap that partially cancels real cogging",
        "rotor-position sampling resolution relative to the cogging period",
        "mesh discretisation at slot openings and magnet edges dominates a small-amplitude quantity",
    ),
}


@dataclass(frozen=True)
class FEAMetricComparison:
    """One analytical value against one FEA value."""

    quantity: str
    unit: str
    basis: str
    analytical_value: float | None
    fea_value: float | None
    absolute_error: float | None
    relative_error_percent: float | None
    reference_scale_name: str | None
    reference_scale_value: float | None
    error_relative_to_reference_scale_percent: float | None
    status: FEAComparisonStatus
    band_statement: str
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class FEASampleStatistics:
    """Aggregate statistics when a comparison spans many samples."""

    sample_count: int
    bias: float
    mean_absolute_error: float
    root_mean_square_error: float
    unit: str


@dataclass(frozen=True)
class FEAComparisonReport:
    """The full comparison for one case and one solver result."""

    schema_version: str
    case_id: str
    analytical_fingerprint_at_comparison: str
    result_case_id: str
    result_analytical_fingerprint: str
    target: FEAValidationTarget
    is_mock: bool
    evidence_admissible: bool
    stale: bool
    stale_reasons: tuple[str, ...]
    metrics: tuple[FEAMetricComparison, ...]
    sample_statistics: FEASampleStatistics | None
    discrepancy_candidates: tuple[str, ...]
    auto_calibration_enabled: bool
    fidelity_tier: str
    approximation_labels: tuple[str, ...]


def _classify(relative_percent: float | None) -> FEAComparisonStatus:
    if relative_percent is None or not math.isfinite(relative_percent):
        return FEAComparisonStatus.NOT_COMPARABLE
    magnitude = abs(relative_percent)
    if magnitude <= PROVISIONAL_CLOSE_AGREEMENT_PERCENT:
        return FEAComparisonStatus.CLOSE_AGREEMENT
    if magnitude <= PROVISIONAL_MODERATE_DEVIATION_PERCENT:
        return FEAComparisonStatus.MODERATE_DEVIATION
    return FEAComparisonStatus.LARGE_DEVIATION


def compare_metric(
    *,
    quantity: str,
    unit: str,
    basis: str,
    analytical_value: float | None,
    fea_value: float | None,
    reference_scale_name: str | None = None,
    reference_scale_value: float | None = None,
    notes: Sequence[str] = (),
) -> FEAMetricComparison:
    """Compare one quantity, refusing to divide by an effectively zero value."""

    note_list = list(notes)
    if analytical_value is None or fea_value is None:
        return FEAMetricComparison(
            quantity=quantity,
            unit=unit,
            basis=basis,
            analytical_value=analytical_value,
            fea_value=fea_value,
            absolute_error=None,
            relative_error_percent=None,
            reference_scale_name=reference_scale_name,
            reference_scale_value=reference_scale_value,
            error_relative_to_reference_scale_percent=None,
            status=FEAComparisonStatus.INSUFFICIENT_DATA,
            band_statement=PROVISIONAL_BAND_STATEMENT,
            notes=tuple(note_list + ["one side of the comparison is unavailable"]),
        )

    absolute_error = fea_value - analytical_value

    scale = abs(reference_scale_value) if reference_scale_value is not None else None
    denominator_floor = (
        scale * DEGENERATE_DENOMINATOR_FRACTION if scale else DEGENERATE_DENOMINATOR_FRACTION
    )
    relative_percent: float | None
    if abs(analytical_value) <= denominator_floor:
        relative_percent = None
        note_list.append(
            "the analytical value is effectively zero, so no relative error is reported "
            "against it; only the absolute difference is meaningful"
        )
    else:
        relative_percent = absolute_error / analytical_value * 100.0

    scaled_percent: float | None = None
    if scale and scale > 0.0:
        scaled_percent = absolute_error / scale * 100.0

    if relative_percent is not None:
        status = _classify(relative_percent)
    elif scaled_percent is not None:
        status = _classify(scaled_percent)
        note_list.append(
            f"classification uses the error relative to {reference_scale_name} because "
            "the analytical value itself is degenerate"
        )
    else:
        status = FEAComparisonStatus.NOT_COMPARABLE

    return FEAMetricComparison(
        quantity=quantity,
        unit=unit,
        basis=basis,
        analytical_value=analytical_value,
        fea_value=fea_value,
        absolute_error=absolute_error,
        relative_error_percent=relative_percent,
        reference_scale_name=reference_scale_name,
        reference_scale_value=reference_scale_value,
        error_relative_to_reference_scale_percent=scaled_percent,
        status=status,
        band_statement=PROVISIONAL_BAND_STATEMENT,
        notes=tuple(note_list),
    )


def sample_statistics(
    analytical: Sequence[float], fea: Sequence[float], unit: str
) -> FEASampleStatistics:
    """Bias, MAE and RMSE across paired samples."""

    left = np.asarray(analytical, dtype=float)
    right = np.asarray(fea, dtype=float)
    if left.size != right.size or left.size == 0:
        raise ValueError("paired sample statistics need equal, non-empty sequences")
    error = right - left
    return FEASampleStatistics(
        sample_count=int(left.size),
        bias=float(np.mean(error)),
        mean_absolute_error=float(np.mean(np.abs(error))),
        root_mean_square_error=float(np.sqrt(np.mean(error**2))),
        unit=unit,
    )


def _ideal_slot_star_winding_factor(case: FEAValidationCase) -> float | None:
    """Fundamental winding factor of the *idealised* winding.

    The slot-EMF star treats coil sides as filaments at slot centres, a whole
    number of slot pitches apart. That is a statement about the slot/pole
    combination, not about the conductor layout a solver meshes. ``None`` when
    the combination has no balanced symmetric winding.

    Phase 10B and 10C used this value to interpret solver output. Phase 10D
    showed the meshed layout is a different winding; see
    :func:`_meshed_geometry_winding_factor`.
    """

    from ..motor_core.winding_factor import (
        WindingFactorError,
        compute_fundamental_winding_factor,
    )

    try:
        breakdown = compute_fundamental_winding_factor(
            slots=case.winding.slot_count,
            pole_pairs=case.winding.pole_pairs,
            coil_span_slots=case.winding.coil_span_slots,
            phases=case.winding.phases,
        )
    except (WindingFactorError, ValueError):
        return None
    return breakdown.fundamental_winding_factor


def _meshed_geometry_winding_factor(case: FEAValidationCase) -> float | None:
    """Fundamental winding factor of the winding the solver actually meshes.

    Measured by projecting the conductor regions of the built slice model onto
    the fundamental, so it follows the real coil-side placement and the finite
    region width rather than an idealised slot-centre filament. ``None`` when the
    model cannot be built for this case.

    This is the factor any inversion of a solved flux linkage must divide by: a
    linkage produced by the meshed winding carries the meshed winding's
    projection, not the star's.
    """

    from .meshed_winding import meshed_winding_factor_for_case

    try:
        return meshed_winding_factor_for_case(case).value
    except (ValueError, KeyError, IndexError, AttributeError):
        return None


def _flux_inversion_winding_factor(case: FEAValidationCase) -> float:
    """The winding factor a solved flux linkage must be divided by.

    The meshed value when it can be measured. Falling back to the entered
    analytical value keeps the row computable for a case whose model cannot be
    built, and the row's notes say which was used, so a fallback can never be
    mistaken for a measurement.
    """

    meshed = _meshed_geometry_winding_factor(case)
    return meshed if meshed is not None else case.winding.winding_factor_analytical


def _stale_reasons(case: FEAValidationCase, result: FEARawResult) -> tuple[str, ...]:
    from .hashing import compute_analytical_fingerprint

    reasons: list[str] = []
    if result.provenance.case_id != case.case_id:
        reasons.append(
            "the solver result was produced for a different case hash; the geometry, "
            "materials, winding, operating point or mesh policy has changed since it ran"
        )
    if result.provenance.analytical_fingerprint != compute_analytical_fingerprint(case):
        reasons.append(
            "the analytical prediction has changed since the solver ran; the FEA "
            "numbers remain valid but this comparison must be recomputed"
        )
    return tuple(reasons)


def build_comparison(
    case: FEAValidationCase, result: FEARawResult
) -> FEAComparisonReport:
    """Compare one analytical prediction against one FEA result."""

    from .hashing import compute_analytical_fingerprint

    if result.target is not case.target:
        raise ValueError("the result and the case validate different quantities")

    stale_reasons = _stale_reasons(case, result)
    analytical = case.analytical
    metrics: list[FEAMetricComparison] = []
    statistics: FEASampleStatistics | None = None

    if case.target is FEAValidationTarget.NO_LOAD_BACK_EMF:
        extraction: FEABackEmfExtraction = extract_back_emf(result)
        metrics.append(
            compare_metric(
                quantity="back_emf_phase_rms",
                unit="volt",
                basis="phase RMS, no-load, at the case mechanical speed",
                analytical_value=analytical.back_emf_phase_rms_v,
                fea_value=extraction.phase_rms_v,
            )
        )
        metrics.append(
            compare_metric(
                quantity="back_emf_line_rms",
                unit="volt",
                basis="line RMS of the non-triplen content, balanced Y",
                analytical_value=analytical.back_emf_line_rms_v,
                fea_value=extraction.line_rms_v,
            )
        )
        metrics.append(
            compare_metric(
                quantity="back_emf_constant_phase_rms",
                unit="volt_second_per_radian_mechanical",
                basis="phase RMS per mechanical rad/s",
                analytical_value=analytical.back_emf_constant_phase_rms_v_per_rad_s,
                fea_value=extraction.back_emf_constant_phase_rms_v_per_rad_s,
            )
        )
        metrics.append(
            compare_metric(
                quantity="flux_per_pole",
                unit="weber",
                basis=(
                    "analytical lumped pole flux against the FEA fundamental flux "
                    "linkage divided by the analytical effective series turns"
                ),
                analytical_value=analytical.flux_per_pole_wb,
                fea_value=(
                    extraction.flux_linkage_fundamental_peak_wb_turn
                    / float(case.winding.turns_per_phase)
                    / _flux_inversion_winding_factor(case)
                    if case.winding.turns_per_phase
                    else None
                ),
                notes=(
                    "this row divides out the analytical turns and the MESHED winding "
                    "factor, so it is not an independent measurement of either",
                    "Phase 10D: a flux linkage produced by the meshed winding carries "
                    "the meshed winding's fundamental projection. Phase 10B and 10C "
                    "divided by the slot-star value instead, which made this row read "
                    "about 10 % high; those historical numbers are superseded, not "
                    "wrong at the time they were recorded",
                    "the analytical value is a flat-top lumped pole flux while the FEA "
                    "value is a fundamental-equivalent flux; the two are different "
                    "quantities and the difference is a convention, not an error",
                ),
            )
        )
        # The back-EMF comparison can only ever test the *product* N * k_w * flux,
        # because that is what flux linkage is. If the entered winding factor does
        # not match the winding the solver actually meshed, an agreeing Ke can be
        # two offsetting errors rather than two correct sub-models, so the two
        # winding factors are reported side by side.
        meshed = _meshed_geometry_winding_factor(case)
        ideal_star = _ideal_slot_star_winding_factor(case)
        metrics.append(
            compare_metric(
                quantity="winding_factor_entered_vs_meshed_geometry",
                unit="dimensionless",
                basis=(
                    "fundamental winding factor entered in the analytical model "
                    "against the fundamental projection of the conductor regions "
                    "the solver actually meshes"
                ),
                analytical_value=case.winding.winding_factor_analytical,
                fea_value=meshed,
                notes=(
                    "the second value is computed from the meshed winding geometry, "
                    "not measured from the field",
                    "a mismatch here means the back-EMF agreement above is the product "
                    "of the winding factor error and the flux error, and neither "
                    "factor is individually validated by it",
                ),
            )
        )
        # The idealised slot star is kept as a separate, explicitly named row.
        # It is the value Phase 10B and 10C interpreted results with, so an
        # auditor reading old evidence needs to see it alongside the meshed one
        # rather than have it silently replaced.
        metrics.append(
            compare_metric(
                quantity="winding_factor_ideal_slot_star_vs_meshed_geometry",
                unit="dimensionless",
                basis=(
                    "idealised slot-EMF-star winding factor, which treats coil "
                    "sides as filaments at slot centres a whole number of slot "
                    "pitches apart, against the meshed conductor projection"
                ),
                analytical_value=ideal_star,
                fea_value=meshed,
                notes=(
                    "DEFINITION_CONVENTION_MISMATCH, not a defect in either value: "
                    "they describe different windings",
                    "the side-by-side double layer places the two sides of a coil one "
                    "slot pitch PLUS one layer width apart, and each side has a finite "
                    "width; the star models neither",
                    "Phase 10B and 10C interpreted solver output with the star value; "
                    "that interpretation is HISTORICAL_INTERPRETATION_SUPERSEDED",
                ),
            )
        )
    elif case.target is FEAValidationTarget.AVERAGE_TORQUE:
        torque: FEATorqueExtraction = extract_average_torque(result)
        metrics.append(
            compare_metric(
                quantity="average_electromagnetic_torque",
                unit="newton_metre",
                basis=(
                    f"mean over one electrical period at {case.operating_point.phase_current_rms_a:.6f} A "
                    "phase RMS with the current vector at 90 electrical degrees (id = 0)"
                ),
                analytical_value=analytical.average_torque_nm,
                fea_value=torque.average_torque_nm,
            )
        )
        if analytical.torque_constant_nm_per_phase_rms_a is not None:
            current = case.operating_point.phase_current_rms_a
            metrics.append(
                compare_metric(
                    quantity="torque_constant_per_phase_rms_ampere",
                    unit="newton_metre_per_ampere",
                    basis="torque per phase RMS ampere at id = 0",
                    analytical_value=analytical.torque_constant_nm_per_phase_rms_a,
                    fea_value=torque.average_torque_nm / current if current > 0.0 else None,
                )
            )
    else:
        cogging: FEACoggingExtraction = extract_cogging(result)
        metrics.append(
            compare_metric(
                quantity="cogging_torque_peak",
                unit="newton_metre",
                basis="single-sided peak amplitude over one cogging period at zero current",
                analytical_value=analytical.cogging_torque_peak_nm,
                fea_value=cogging.amplitude_nm,
                reference_scale_name="analytical_average_torque",
                reference_scale_value=analytical.average_torque_nm,
                notes=(analytical.cogging_model_provenance,),
            )
        )
        metrics.append(
            compare_metric(
                quantity="cogging_torque_peak_to_peak",
                unit="newton_metre",
                basis="peak-to-peak over one cogging period at zero current",
                analytical_value=2.0 * analytical.cogging_torque_peak_nm,
                fea_value=cogging.peak_to_peak_nm,
                reference_scale_name="analytical_average_torque",
                reference_scale_value=analytical.average_torque_nm,
                notes=(
                    "the analytical model publishes only a peak amplitude; the "
                    "peak-to-peak reference doubles it and assumes a symmetric waveform",
                ),
            )
        )

    return FEAComparisonReport(
        schema_version=FEA_COMPARISON_SCHEMA_VERSION,
        case_id=case.case_id,
        analytical_fingerprint_at_comparison=compute_analytical_fingerprint(case),
        result_case_id=result.provenance.case_id,
        result_analytical_fingerprint=result.provenance.analytical_fingerprint,
        target=case.target,
        is_mock=result.is_mock,
        # Mock data is never admissible as validation evidence, and neither is a
        # result whose case has moved on.
        evidence_admissible=(not result.is_mock) and not stale_reasons,
        stale=bool(stale_reasons),
        stale_reasons=stale_reasons,
        metrics=tuple(metrics),
        sample_statistics=statistics,
        discrepancy_candidates=DISCREPANCY_CANDIDATES[case.target],
        auto_calibration_enabled=AUTO_CALIBRATION_ENABLED,
        fidelity_tier=case.supportability.fidelity_tier,
        approximation_labels=case.supportability.approximation_labels,
    )
