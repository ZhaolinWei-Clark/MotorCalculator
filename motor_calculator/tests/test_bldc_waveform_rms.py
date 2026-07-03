"""Waveform and RMS tests for ideal BLDC 120-degree revised semantics."""

from __future__ import annotations

import math

from motor_core import (
    MotorControlMode,
    calculate_bldc_line_to_line_back_emf_peak_from_phase_flat_top_v,
    calculate_bldc_line_to_line_back_emf_rms_from_phase_flat_top_v,
    calculate_bldc_phase_back_emf_rms_from_flat_top_v,
    normalized_bldc_line_to_line_back_emf,
    normalized_bldc_line_to_line_back_emf_rms,
    normalized_bldc_phase_back_emf,
    normalized_bldc_phase_back_emf_rms,
)

REL_TOL = 1e-8
ABS_TOL = 1e-10


def test_bldc_phase_back_emf_is_periodic_and_piecewise_defined():
    assert math.isclose(normalized_bldc_phase_back_emf(0.0), 0.0, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(normalized_bldc_phase_back_emf(math.pi / 6.0), 1.0, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(normalized_bldc_phase_back_emf(math.pi / 2.0), 1.0, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(normalized_bldc_phase_back_emf(math.pi), 0.0, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(normalized_bldc_phase_back_emf(3.0 * math.pi / 2.0), -1.0, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(normalized_bldc_phase_back_emf(2.0 * math.pi), 0.0, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(
        normalized_bldc_phase_back_emf(0.37),
        normalized_bldc_phase_back_emf(0.37 + 2.0 * math.pi),
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )


def test_bldc_line_to_line_waveform_has_expected_peak_and_phase_shift():
    assert math.isclose(normalized_bldc_line_to_line_back_emf(0.0), 1.0, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(normalized_bldc_line_to_line_back_emf(math.pi / 3.0), 2.0, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(normalized_bldc_line_to_line_back_emf(math.pi), -1.0, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(
        normalized_bldc_line_to_line_back_emf(1.1),
        normalized_bldc_line_to_line_back_emf(1.1 + 2.0 * math.pi),
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )


def test_bldc_phase_back_emf_rms_matches_piecewise_analytic_value():
    phase_flat_top_back_emf_v = 18.0
    expected_rms_v = phase_flat_top_back_emf_v * math.sqrt(7.0) / 3.0

    assert math.isclose(normalized_bldc_phase_back_emf_rms(), math.sqrt(7.0) / 3.0, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(
        calculate_bldc_phase_back_emf_rms_from_flat_top_v(
            phase_flat_top_back_emf_v=phase_flat_top_back_emf_v,
            control_mode=MotorControlMode.BLDC_120_DEGREE,
        ),
        expected_rms_v,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )


def test_bldc_line_to_line_back_emf_rms_matches_piecewise_analytic_value():
    phase_flat_top_back_emf_v = 18.0
    expected_line_rms_v = phase_flat_top_back_emf_v * 2.0 * math.sqrt(5.0) / 3.0

    assert math.isclose(normalized_bldc_line_to_line_back_emf_rms(), 2.0 * math.sqrt(5.0) / 3.0, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(
        calculate_bldc_line_to_line_back_emf_rms_from_phase_flat_top_v(
            phase_flat_top_back_emf_v=phase_flat_top_back_emf_v,
            control_mode=MotorControlMode.BLDC_120_DEGREE,
        ),
        expected_line_rms_v,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        calculate_bldc_line_to_line_back_emf_peak_from_phase_flat_top_v(
            phase_flat_top_back_emf_v=phase_flat_top_back_emf_v,
            control_mode=MotorControlMode.BLDC_120_DEGREE,
        ),
        2.0 * phase_flat_top_back_emf_v,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
