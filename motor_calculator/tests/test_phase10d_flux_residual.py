"""Phase 10D: direct air-gap extraction, harmonic analysis and residual budget.

These tests cover the diagnostic machinery, not a solver run. The two tests that
consume real FEMM output read the committed Phase 10D evidence rather than
re-solving, so the suite stays fast and deterministic.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from motor_calculator.fea.airgap_probe import (
    AIRGAP_CSV_HEADER,
    AIRGAP_PROBE_VERSION,
    AirgapScan,
    absolute_pole_flux_wb,
    fundamental_flux_per_pole_wb,
    parse_airgap_csv,
    rectangular_to_fundamental_form_factor,
    signed_pole_flux_wb,
    spatial_harmonics,
    vector_potential_fundamental_flux_per_pole_wb,
    vector_potential_peak_to_peak_flux_wb,
)
from motor_calculator.fea.flux_budget import (
    FLUX_BUDGET_SCHEMA_VERSION,
    build_flux_residual_budget,
    meshed_winding_factor,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = REPOSITORY_ROOT / "validation_data" / "fea_results" / "phase10d_flux_diagnosis"

POLE_PAIRS = 8
SPAN_M = 0.3298672286269283
RADIAL_LENGTH_M = 0.035
PEAK_T = 0.6790450928381965
ALPHA_P = 0.7


def _rectangular_scan(samples: int = 4096, alpha: float = ALPHA_P) -> AirgapScan:
    """An ideal alternating flat-top field, for checking the maths exactly."""

    x = np.arange(samples) * SPAN_M / samples
    tau = SPAN_M / (2 * POLE_PAIRS)
    within = np.mod(x, 2.0 * tau)
    b = np.where(
        np.abs(within - tau * 0.5) <= alpha * tau / 2.0,
        PEAK_T,
        np.where(np.abs(within - tau * 1.5) <= alpha * tau / 2.0, -PEAK_T, 0.0),
    )
    return AirgapScan(
        plane_y_m=0.0,
        x_m=tuple(x),
        bx_t=tuple(np.zeros(samples)),
        by_t=tuple(b),
        span_m=SPAN_M,
        pole_pairs=POLE_PAIRS,
        radial_length_m=RADIAL_LENGTH_M,
    )


# ---------------------------------------------------------------------------
# Harmonic decomposition
# ---------------------------------------------------------------------------


def test_a_pure_sinusoid_has_no_harmonic_content():
    samples = 2048
    x = np.arange(samples) * SPAN_M / samples
    b = PEAK_T * np.cos(2.0 * math.pi * POLE_PAIRS * x / SPAN_M)
    scan = AirgapScan(
        plane_y_m=0.0,
        x_m=tuple(x),
        bx_t=tuple(np.zeros(samples)),
        by_t=tuple(b),
        span_m=SPAN_M,
        pole_pairs=POLE_PAIRS,
        radial_length_m=RADIAL_LENGTH_M,
    )
    harmonics = spatial_harmonics(scan)
    assert harmonics.fundamental_amplitude_t == pytest.approx(PEAK_T, rel=1e-9)
    assert harmonics.total_harmonic_distortion < 1e-9
    # A sinusoid's fundamental is its peak.
    assert harmonics.peak_t == pytest.approx(harmonics.fundamental_amplitude_t, rel=1e-6)


def test_a_rectangular_pole_reproduces_the_textbook_fourier_amplitude():
    scan = _rectangular_scan()
    harmonics = spatial_harmonics(scan)
    expected = (4.0 / math.pi) * PEAK_T * math.sin(ALPHA_P * math.pi / 2.0)
    assert harmonics.fundamental_amplitude_t == pytest.approx(expected, rel=2e-3)
    # A 0.7 rectangle is materially non-sinusoidal; this is what the analytical
    # model assumes the field looks like.
    assert harmonics.total_harmonic_distortion > 0.2


def test_harmonic_orders_are_relative_to_the_pole_pair_fundamental():
    scan = _rectangular_scan()
    harmonics = spatial_harmonics(scan)
    # A symmetric alternating waveform has no even harmonics.
    for order in (2, 4, 6):
        assert harmonics.amplitude_ratio(order) < 1e-6
    # and a 0.7 arc has a substantial third.
    assert harmonics.amplitude_ratio(3) > 0.05


# ---------------------------------------------------------------------------
# Flux conventions
# ---------------------------------------------------------------------------


def test_the_three_flux_conventions_are_different_quantities():
    scan = _rectangular_scan()
    flat = PEAK_T * ALPHA_P * scan.pole_pitch_m * RADIAL_LENGTH_M
    assert absolute_pole_flux_wb(scan) == pytest.approx(flat, rel=2e-3)
    assert abs(signed_pole_flux_wb(scan)) == pytest.approx(flat, rel=2e-3)
    fundamental = fundamental_flux_per_pole_wb(scan)
    # For alpha_p = 0.7 the fundamental exceeds the flat top; they are not
    # interchangeable and the sign of the difference depends on the arc.
    assert fundamental > flat
    assert fundamental / flat == pytest.approx(
        rectangular_to_fundamental_form_factor(ALPHA_P), rel=2e-3
    )


def test_the_form_factor_changes_sign_across_the_pole_arc_range():
    # Narrow arcs concentrate the fundamental, wide arcs dilute it. A model that
    # ignores the conversion is wrong in a direction that depends on geometry.
    assert rectangular_to_fundamental_form_factor(0.6) > 1.0
    assert rectangular_to_fundamental_form_factor(0.7) > 1.0
    assert rectangular_to_fundamental_form_factor(0.8) < 1.0
    assert rectangular_to_fundamental_form_factor(1.0) == pytest.approx(
        8.0 / math.pi**2, rel=1e-12
    )


def test_the_form_factor_rejects_an_impossible_pole_arc():
    with pytest.raises(ValueError):
        rectangular_to_fundamental_form_factor(0.0)
    with pytest.raises(ValueError):
        rectangular_to_fundamental_form_factor(1.5)


def test_signed_pole_flux_alternates_and_absolute_flux_does_not():
    scan = _rectangular_scan()
    first = signed_pole_flux_wb(scan, pole_index=0)
    second = signed_pole_flux_wb(scan, pole_index=1)
    assert first * second < 0.0
    assert absolute_pole_flux_wb(scan) > 0.0


def test_vector_potential_and_flux_density_routes_are_the_same_quantity():
    """``A1 = B1 * tau / pi``, so both routes must agree for the fundamental."""

    samples = 4096
    x = np.arange(samples) * SPAN_M / samples
    k = 2.0 * math.pi * POLE_PAIRS / SPAN_M
    b = PEAK_T * np.cos(k * x)
    a = -(PEAK_T / k) * np.sin(k * x)
    scan = AirgapScan(
        plane_y_m=0.0,
        x_m=tuple(x),
        bx_t=tuple(np.zeros(samples)),
        by_t=tuple(b),
        span_m=SPAN_M,
        pole_pairs=POLE_PAIRS,
        radial_length_m=RADIAL_LENGTH_M,
        a_wb_per_m=tuple(a),
    )
    assert vector_potential_fundamental_flux_per_pole_wb(scan) == pytest.approx(
        fundamental_flux_per_pole_wb(scan), rel=1e-9
    )
    assert vector_potential_peak_to_peak_flux_wb(scan) > 0.0


def test_a_scan_without_vector_potential_refuses_the_A_route():
    scan = _rectangular_scan()
    with pytest.raises(ValueError):
        vector_potential_fundamental_flux_per_pole_wb(scan)


# ---------------------------------------------------------------------------
# CSV parsing and sign conventions
# ---------------------------------------------------------------------------


def test_the_csv_parser_groups_planes_and_keeps_x_order():
    text = AIRGAP_CSV_HEADER + "\n" + "\n".join(
        f"{plane},{i * SPAN_M / 8},{0.1 * i},{0.0},{0.5 - 0.1 * i}"
        for plane in (0.001, 0.0)
        for i in range(8)
    )
    scans = parse_airgap_csv(
        text, span_m=SPAN_M, pole_pairs=1, radial_length_m=RADIAL_LENGTH_M
    )
    assert [s.plane_y_m for s in scans] == [0.0, 0.001]
    assert list(scans[0].x_m) == sorted(scans[0].x_m)
    assert len(scans[0].a_wb_per_m) == 8


def test_a_malformed_or_headerless_csv_is_rejected():
    with pytest.raises(ValueError):
        parse_airgap_csv("garbage\n1,2,3,4,5", span_m=SPAN_M, pole_pairs=1, radial_length_m=1.0)
    with pytest.raises(ValueError):
        parse_airgap_csv(
            AIRGAP_CSV_HEADER + "\n0.0,0.0,0.0\n",
            span_m=SPAN_M,
            pole_pairs=1,
            radial_length_m=1.0,
        )


def test_a_scan_rejects_inconsistent_or_degenerate_input():
    with pytest.raises(ValueError):
        AirgapScan(0.0, (0.0,), (0.0,), (0.0,), SPAN_M, POLE_PAIRS, RADIAL_LENGTH_M)
    with pytest.raises(ValueError):
        AirgapScan(
            0.0, tuple(range(8)), tuple(range(8)), tuple(range(7)),
            SPAN_M, POLE_PAIRS, RADIAL_LENGTH_M,
        )
    with pytest.raises(ValueError):
        AirgapScan(
            0.0, tuple(range(8)), tuple(range(8)), tuple(range(8)),
            SPAN_M, 0, RADIAL_LENGTH_M,
        )


# ---------------------------------------------------------------------------
# Meshed winding factor
# ---------------------------------------------------------------------------


def test_a_full_pitch_filament_coil_has_unit_pitch_factor():
    tau = 0.02
    assert meshed_winding_factor(
        coil_pitch_m=tau, coil_side_width_m=1e-9, pole_pitch_m=tau
    ) == pytest.approx(1.0, rel=1e-6)


def test_a_two_thirds_pitch_coil_reproduces_the_slot_star_value():
    tau = 0.020616702
    assert meshed_winding_factor(
        coil_pitch_m=tau * 2.0 / 3.0, coil_side_width_m=1e-9, pole_pitch_m=tau
    ) == pytest.approx(math.sqrt(3.0) / 2.0, rel=1e-6)


def test_finite_coil_side_width_always_reduces_the_winding_factor():
    tau = 0.020616702
    narrow = meshed_winding_factor(
        coil_pitch_m=0.0172, coil_side_width_m=1e-9, pole_pitch_m=tau
    )
    wide = meshed_winding_factor(
        coil_pitch_m=0.0172, coil_side_width_m=0.0035, pole_pitch_m=tau
    )
    assert wide < narrow


def test_meshed_winding_factor_rejects_nonpositive_geometry():
    with pytest.raises(ValueError):
        meshed_winding_factor(coil_pitch_m=0.0, coil_side_width_m=0.001, pole_pitch_m=0.02)
    with pytest.raises(ValueError):
        meshed_winding_factor(coil_pitch_m=0.01, coil_side_width_m=-1.0, pole_pitch_m=0.02)


# ---------------------------------------------------------------------------
# Residual budget
# ---------------------------------------------------------------------------


def _budget(**overrides):
    kwargs = dict(
        winding_factor_meshed=0.955752007,
        winding_factor_assumed=0.8660254037844386,
        analytical_flat_top_flux_wb=0.0003429919194211033,
        fea_fundamental_flux_wb=0.0003328081908,
        pole_arc_coefficient=0.7,
        sine_emf_factor=4.44,
        observed_ke_ratio=1.071543045776,
    )
    kwargs.update(overrides)
    return build_flux_residual_budget(**kwargs)


def test_the_budget_reconstructs_the_observed_residual():
    budget = _budget()
    assert budget.schema_version == FLUX_BUDGET_SCHEMA_VERSION
    assert budget.is_fully_decomposed
    assert abs(budget.unresolved_remainder) < 1e-4


def test_the_budget_factors_multiply_rather_than_add():
    budget = _budget()
    additive = sum(factor - 1.0 for _, factor, _ in budget.as_rows())
    assert budget.reconstructed_ratio - 1.0 != pytest.approx(additive, rel=1e-6)


def test_the_budget_is_ordered_by_contribution_size():
    rows = _budget().as_rows()
    magnitudes = [abs(factor - 1.0) for _, factor, _ in rows]
    assert magnitudes == sorted(magnitudes, reverse=True)
    assert rows[0][0].startswith("winding factor")


def test_a_broken_budget_reports_an_unresolved_remainder_instead_of_hiding_it():
    budget = _budget(fea_fundamental_flux_wb=0.0004)
    assert not budget.is_fully_decomposed
    assert abs(budget.unresolved_remainder) > 0.01


def test_the_budget_rejects_impossible_inputs():
    with pytest.raises(ValueError):
        _budget(winding_factor_meshed=1.5)
    with pytest.raises(ValueError):
        _budget(analytical_flat_top_flux_wb=0.0)
    with pytest.raises(ValueError):
        _budget(pole_arc_coefficient=0.0)


def test_the_budget_never_stores_a_correction_factor():
    """The budget reports ratios; it must not expose a value to apply."""

    budget = _budget()
    names = set(vars(budget))
    for forbidden in ("correction", "calibration", "tuned", "fitted", "scale_factor"):
        assert not any(forbidden in name for name in names)


# ---------------------------------------------------------------------------
# Committed Phase 10D evidence
# ---------------------------------------------------------------------------


def test_the_committed_budget_evidence_is_fully_decomposed():
    payload = json.loads(
        (EVIDENCE / "phase10d_residual_budget.json").read_text(encoding="utf-8")
    )
    assert payload["diagnostic_only"] is True
    assert payload["calibration_performed"] is False
    assert payload["production_defaults_mutated"] is False
    assert abs(payload["budget"]["unresolved_remainder_percent"]) < 0.05


def test_the_committed_evidence_shows_the_two_winding_factor_routes_agreeing():
    payload = json.loads(
        (EVIDENCE / "phase10d_winding_factor_truth.json").read_text(encoding="utf-8")
    )
    assert abs(payload["winding_factor_routes_agreement_percent"]) < 1.0
    # The meshed winding is materially different from the slot-star assumption;
    # this is the Phase 10D finding and it must not silently regress.
    assert payload["meshed_over_star_ratio"] > 1.05
    geometric = meshed_winding_factor(
        coil_pitch_m=payload["meshed_coil_pitch_m"],
        coil_side_width_m=payload["coil_side_width_m"],
        pole_pitch_m=payload["pole_pitch_m"],
    )
    assert geometric == pytest.approx(payload["winding_factor_meshed_geometry"], rel=1e-9)


def test_the_committed_evidence_records_peak_flux_density_agreement():
    payload = json.loads(
        (EVIDENCE / "phase10d_residual_budget.json").read_text(encoding="utf-8")
    )
    # The lumped magnetic circuit predicts the peak air-gap flux density well;
    # the residual is waveform and convention, not amplitude.
    assert abs(payload["peak_flux_density_agreement_percent"]) < 0.5
    assert payload["femm_b1_over_peak"] < payload["ideal_rectangle_b1_over_peak"]


def test_the_probe_version_is_pinned():
    assert AIRGAP_PROBE_VERSION == "phase10d.femm.airgap.v2"
    assert AIRGAP_CSV_HEADER == "plane_y_m,x_m,a_wb_per_m,bx_t,by_t"


def test_phase10d_did_not_mutate_any_production_default():
    """Phase 10D is diagnostic. The shipped inputs must be untouched."""

    from motor_calculator.fea.reference_cases import PHASE10A_REFERENCE_PARAMETERS

    assert PHASE10A_REFERENCE_PARAMETERS["sigma_m"] == 1.15
    assert PHASE10A_REFERENCE_PARAMETERS["mu_r_mag"] == 1.05
    assert PHASE10A_REFERENCE_PARAMETERS["g_side"] == 1.0
    assert PHASE10A_REFERENCE_PARAMETERS["h_coil"] == 5.0
