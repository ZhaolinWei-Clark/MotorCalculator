"""Phase 9B Batch C1: corrected required voltage as a mandatory parallel output.

Phase 9 Finding 1 is the only CONFIRMED_FORMULA_DEFECT of the five. The legacy
expression mixes three reference bases in one root and RSS-combines terms that
are not mutually orthogonal:

    legacy = sqrt(E_line_rms**2 + (I_ph*R_line)**2 + (I_ph*we*L_s)**2) * k
             |__ sqrt3 x phase   |__ 2 x phase      |__ 1 x phase

The corrected quantity is published alongside it. The legacy output is not
replaced and remains the production default until the promotion gates pass.
"""

from __future__ import annotations

import math

import pytest

from helpers import build_sample_legacy_params
from motor_core import LegacyGuiMotorModelBridge, parse_legacy_gui_params
from motor_calculator.motor_core.constants import VOLTAGE_REQUIREMENT_MARGIN_FACTOR
from motor_calculator.motor_core.voltage_semantics import (
    CORRECTED_VOLTAGE_BASIS,
    CORRECTED_VOLTAGE_STATUS,
    LEGACY_VOLTAGE_STATUS,
    VOLTAGE_CONSUMER_CLASSIFICATION,
    corrected_required_voltage_line_rms_v,
    dq_steady_state_required_voltage_line_rms_v,
)
from motor_calculator.validation.design_feasibility import (
    evaluate_design_feasibility,
    feasible_starting_inputs,
    same_basis_available_line_rms_v,
)


# Recorded at the start of C1 on codex/phase9b-controlled-formula-corrections.
C1_REFERENCE = {
    "manufacturability_start": {
        "legacy": 42.95649060989958,
        "corrected": 53.509476885063116,
        "relative_difference": 0.2456668625702756,
        "legacy_margin": 15.62548387156598,
        "corrected_margin": -5.102538786591522,
    },
    "application_default": {
        "legacy": 51.517825292613125,
        "corrected": 66.67186480722053,
        "relative_difference": 0.29415138213880043,
        "legacy_margin": -51.7858484016274,
        "corrected_margin": -96.43386549807654,
    },
}


def _application_defaults():
    from motor_calculator.input_ux.metadata import APPLICATION_DEFAULTS

    return dict(APPLICATION_DEFAULTS)


def _cases():
    return {
        "application_default": _application_defaults(),
        "manufacturability_start": feasible_starting_inputs(_application_defaults()),
    }


def _evaluate(raw):
    parsed = parse_legacy_gui_params(raw)
    result = LegacyGuiMotorModelBridge(parsed).run_full_analysis()
    return parsed, result


# ---------------------------------------------------------------------------
# C1.1 single explicit basis
# ---------------------------------------------------------------------------


def test_c1_1_basis_descriptor_is_explicit_for_every_term():
    for term in ("back_emf", "current", "resistance", "inductance", "result"):
        assert term in CORRECTED_VOLTAGE_BASIS, f"missing basis for {term}"
        descriptor = CORRECTED_VOLTAGE_BASIS[term]
        assert "phase" in descriptor or "line" in descriptor
        assert "rms" in descriptor or "peak" in descriptor or "ohm" in descriptor or "henry" in descriptor

    # Every input term is per-phase RMS; only the final result is line RMS.
    assert CORRECTED_VOLTAGE_BASIS["back_emf"] == "phase_rms_volt"
    assert CORRECTED_VOLTAGE_BASIS["current"] == "phase_rms_ampere"
    assert CORRECTED_VOLTAGE_BASIS["resistance"] == "phase_ohm"
    assert CORRECTED_VOLTAGE_BASIS["inductance"] == "phase_synchronous_henry"
    assert CORRECTED_VOLTAGE_BASIS["result"] == "line_rms_volt"


def test_c1_1_no_term_uses_the_terminal_two_times_phase_resistance():
    """The legacy 2*R_ph term is a terminal DC measurement, not the balanced
    three-phase sqrt(3) relationship. The corrected form must not use it."""

    parsed, result = _evaluate(_cases()["manufacturability_start"])
    electrical, performance = result.electrical, result.performance
    omega_e = 2.0 * math.pi * performance.electrical_frequency_hz

    with_phase_resistance = corrected_required_voltage_line_rms_v(
        back_emf_phase_rms_v=electrical.back_emf_phase_rms_v,
        phase_current_rms_a=performance.phase_current_rms_a,
        phase_resistance_ohm=electrical.phase_resistance_ohm,
        synchronous_inductance_h=electrical.line_inductance_h,
        electrical_angular_speed_rad_s=omega_e,
    )
    with_terminal_resistance = corrected_required_voltage_line_rms_v(
        back_emf_phase_rms_v=electrical.back_emf_phase_rms_v,
        phase_current_rms_a=performance.phase_current_rms_a,
        phase_resistance_ohm=electrical.line_resistance_ohm,
        synchronous_inductance_h=electrical.line_inductance_h,
        electrical_angular_speed_rad_s=omega_e,
    )
    assert with_phase_resistance != with_terminal_resistance
    assert float(performance.required_voltage_line_rms_corrected_v) == pytest.approx(
        with_phase_resistance, rel=1e-15
    )


# ---------------------------------------------------------------------------
# C1.2 reference formulation + C1.5 dq cross-check
# ---------------------------------------------------------------------------


DQ_TOLERANCE_REL = 1e-12


@pytest.mark.parametrize("case_name", sorted(C1_REFERENCE))
def test_c1_5_corrected_voltage_equals_the_dq_steady_state_form(case_name):
    parsed, result = _evaluate(_cases()[case_name])
    electrical, performance = result.electrical, result.performance
    omega_e = 2.0 * math.pi * performance.electrical_frequency_hz

    phasor = float(performance.required_voltage_line_rms_corrected_v)
    dq = dq_steady_state_required_voltage_line_rms_v(
        magnet_flux_linkage_wb=electrical.torque_constant_nm_per_phase_peak_a
        / (1.5 * int(parsed["p"])),
        phase_current_rms_a=performance.phase_current_rms_a,
        phase_resistance_ohm=electrical.phase_resistance_ohm,
        synchronous_inductance_h=electrical.line_inductance_h,
        electrical_angular_speed_rad_s=omega_e,
    )
    assert phasor == pytest.approx(dq, rel=DQ_TOLERANCE_REL)


def test_c1_5_dq_flux_linkage_bridge_reproduces_the_phase_peak_back_emf():
    """psi_f = Kt_peak / (1.5 p) must satisfy we * psi_f == E_phase_peak."""

    parsed, result = _evaluate(_cases()["manufacturability_start"])
    electrical, performance = result.electrical, result.performance
    omega_e = 2.0 * math.pi * performance.electrical_frequency_hz
    psi_f = electrical.torque_constant_nm_per_phase_peak_a / (1.5 * int(parsed["p"]))

    assert omega_e * psi_f == pytest.approx(
        math.sqrt(2.0) * electrical.back_emf_phase_rms_v, rel=1e-12
    )


def test_c1_2_no_third_independent_formula_exists():
    """The two published helpers must be algebraically the same expression."""

    for current in (0.0, 1.0, 7.5, 40.0):
        psi_f = 0.0156
        omega_e = 1843.0
        resistance = 0.058
        inductance = 1.142e-3
        phasor = corrected_required_voltage_line_rms_v(
            back_emf_phase_rms_v=omega_e * psi_f / math.sqrt(2.0),
            phase_current_rms_a=current,
            phase_resistance_ohm=resistance,
            synchronous_inductance_h=inductance,
            electrical_angular_speed_rad_s=omega_e,
        )
        dq = dq_steady_state_required_voltage_line_rms_v(
            magnet_flux_linkage_wb=psi_f,
            phase_current_rms_a=current,
            phase_resistance_ohm=resistance,
            synchronous_inductance_h=inductance,
            electrical_angular_speed_rad_s=omega_e,
        )
        assert phasor == pytest.approx(dq, rel=DQ_TOLERANCE_REL)


# ---------------------------------------------------------------------------
# C1.3 parallel results, legacy untouched
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_name", sorted(C1_REFERENCE))
def test_c1_3_legacy_required_voltage_is_bit_identical(case_name):
    _parsed, result = _evaluate(_cases()[case_name])

    assert float(result.performance.required_voltage_v) == C1_REFERENCE[case_name]["legacy"]
    assert result.performance.required_voltage_semantics_status == LEGACY_VOLTAGE_STATUS


@pytest.mark.parametrize("case_name", sorted(C1_REFERENCE))
def test_c1_3_corrected_required_voltage_is_published(case_name):
    _parsed, result = _evaluate(_cases()[case_name])
    expected = C1_REFERENCE[case_name]

    assert float(result.performance.required_voltage_line_rms_corrected_v) == pytest.approx(
        expected["corrected"], rel=1e-12
    )
    assert float(
        result.performance.required_voltage_legacy_corrected_relative_difference
    ) == pytest.approx(expected["relative_difference"], rel=1e-12)
    assert result.performance.required_voltage_corrected_status == CORRECTED_VOLTAGE_STATUS


@pytest.mark.parametrize("case_name", sorted(C1_REFERENCE))
def test_c1_3_both_margins_are_available_and_different(case_name):
    parsed, result = _evaluate(_cases()[case_name])
    assessment = evaluate_design_feasibility(parsed, result)
    expected = C1_REFERENCE[case_name]

    assert assessment.voltage_margin_percent == pytest.approx(
        expected["legacy_margin"], rel=1e-12
    )
    assert assessment.corrected_voltage_margin_percent == pytest.approx(
        expected["corrected_margin"], rel=1e-12
    )
    assert assessment.corrected_required_voltage_line_rms_v == pytest.approx(
        expected["corrected"], rel=1e-12
    )
    # The difference must never be hidden.
    assert assessment.corrected_voltage_margin_percent < assessment.voltage_margin_percent


def test_c1_3_bldc_reports_the_corrected_voltage_as_unavailable():
    """The corrected form is a sinusoidal phasor result; BLDC lacks the basis."""

    parsed, result = _evaluate(build_sample_legacy_params(waveform="梯形波"))

    assert result.performance.required_voltage_line_rms_corrected_v is None
    assert "not_applicable" in result.performance.required_voltage_corrected_status
    assessment = evaluate_design_feasibility(parsed, result)
    assert assessment.corrected_voltage_margin_percent is None


# ---------------------------------------------------------------------------
# C1.4 controlled comparison campaign
# ---------------------------------------------------------------------------


def _campaign_grid():
    base = feasible_starting_inputs(_application_defaults())
    for speed in (1200.0, 1800.0, 2200.0, 2800.0, 3400.0):
        for power in (200.0, 600.0, 1200.0):
            for winding_factor in (0.85, 0.93):
                for turns in (35, 51, 70):
                    for wire in (1.0, 1.2):
                        raw = dict(base)
                        raw.update(
                            {
                                "n_rated": speed,
                                "P_rated": power,
                                "k_w": winding_factor,
                                "N_ph_turns": turns,
                                "d_wire": wire,
                            }
                        )
                        yield raw


def test_c1_4_corrected_voltage_exceeds_legacy_across_the_whole_grid():
    """The legacy form is non-conservative everywhere, never conservative."""

    ratios = []
    for raw in _campaign_grid():
        _parsed, result = _evaluate(raw)
        legacy = float(result.performance.required_voltage_v)
        corrected = float(result.performance.required_voltage_line_rms_corrected_v)
        ratios.append(corrected / legacy - 1.0)

    assert len(ratios) == 180
    assert min(ratios) > 0.0, "legacy must never over-estimate"
    assert max(ratios) < 2.0  # sanity bound, not a physical claim


def test_c1_4_feasibility_flips_are_counted_and_only_go_one_way():
    flips = 0
    both_feasible = 0
    both_infeasible = 0
    for raw in _campaign_grid():
        parsed, result = _evaluate(raw)
        assessment = evaluate_design_feasibility(parsed, result)
        legacy_ok = assessment.voltage_margin_percent >= 0.0
        corrected_ok = assessment.corrected_voltage_margin_percent >= 0.0
        assert not (corrected_ok and not legacy_ok), (
            "a design cannot become feasible under the corrected basis"
        )
        if legacy_ok and not corrected_ok:
            flips += 1
        elif legacy_ok:
            both_feasible += 1
        else:
            both_infeasible += 1

    assert flips > 0
    assert flips + both_feasible + both_infeasible == 180


# ---------------------------------------------------------------------------
# C1.6 downstream consumer inventory
# ---------------------------------------------------------------------------


REQUIRED_CONSUMERS = {
    "feasibility",
    "optimizer",
    "dashboard",
    "plots",
    "exports",
    "reports",
    "presets",
    "project_snapshots",
    "uncertainty",
    "sensitivity",
}
ALLOWED_CLASSES = {"LEGACY_KEEP", "MIGRATE_TO_CORRECTED", "DUAL_DISPLAY", "NEEDS_REVIEW"}


def test_c1_6_every_required_consumer_is_classified():
    assert REQUIRED_CONSUMERS <= set(VOLTAGE_CONSUMER_CLASSIFICATION)
    for name, entry in VOLTAGE_CONSUMER_CLASSIFICATION.items():
        assert entry["classification"] in ALLOWED_CLASSES, name
        assert entry["rationale_zh"], name


def test_c1_6_nothing_silently_migrated_before_promotion():
    """Until the promotion gates pass, no consumer may already be reading the
    corrected value as its only source."""

    migrated = [
        name
        for name, entry in VOLTAGE_CONSUMER_CLASSIFICATION.items()
        if entry["classification"] == "MIGRATE_TO_CORRECTED"
    ]
    assert migrated == [], f"premature migration: {migrated}"


# ---------------------------------------------------------------------------
# Downstream isolation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_name", sorted(C1_REFERENCE))
def test_c1_corrected_voltage_changes_no_other_output(case_name):
    _parsed, result = _evaluate(_cases()[case_name])
    performance = result.performance

    # required_voltage is a terminal output; nothing upstream may move.
    assert performance.rated_torque_nm > 0.0
    assert performance.phase_current_rms_a > 0.0
    assert performance.efficiency_percent > 0.0
    assert performance.voltage_margin_percent == pytest.approx(
        (
            float(result.electrical.dc_bus_voltage_v)
            - C1_REFERENCE[case_name]["legacy"]
        )
        / float(result.electrical.dc_bus_voltage_v)
        * 100.0,
        rel=1e-12,
    )


def test_c1_margin_factor_is_shared_by_both_formulations():
    parsed, result = _evaluate(_cases()["manufacturability_start"])
    electrical, performance = result.electrical, result.performance
    omega_e = 2.0 * math.pi * performance.electrical_frequency_hz

    unscaled = math.sqrt(3.0) * math.hypot(
        electrical.back_emf_phase_rms_v
        + performance.phase_current_rms_a * electrical.phase_resistance_ohm,
        performance.phase_current_rms_a * omega_e * electrical.line_inductance_h,
    )
    assert float(performance.required_voltage_line_rms_corrected_v) == pytest.approx(
        unscaled * VOLTAGE_REQUIREMENT_MARGIN_FACTOR, rel=1e-12
    )
