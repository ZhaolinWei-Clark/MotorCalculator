"""Current-semantics tests for ideal BLDC 120-degree revised semantics."""

from __future__ import annotations

import math

from motor_core import (
    MotorControlMode,
    calculate_bldc_conduction_current_from_phase_rms_current,
    calculate_bldc_line_current_rms_from_conduction_current,
    calculate_bldc_phase_current_rms_from_conduction_current,
    normalized_bldc_phase_current,
    normalized_bldc_phase_current_rms,
)

REL_TOL = 1e-8
ABS_TOL = 1e-10


def test_bldc_phase_current_is_periodic_and_has_120_degree_conduction_windows():
    assert math.isclose(normalized_bldc_phase_current(0.0), 0.0, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(normalized_bldc_phase_current(math.pi / 3.0), 1.0, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(normalized_bldc_phase_current(math.pi), 0.0, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(normalized_bldc_phase_current(4.0 * math.pi / 3.0), -1.0, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(
        normalized_bldc_phase_current(0.73),
        normalized_bldc_phase_current(0.73 + 2.0 * math.pi),
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )


def test_bldc_phase_current_rms_matches_120_degree_duty_cycle():
    conduction_current_a = 15.0
    expected_phase_rms_a = conduction_current_a * math.sqrt(2.0 / 3.0)

    assert math.isclose(normalized_bldc_phase_current_rms(), math.sqrt(2.0 / 3.0), rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(
        calculate_bldc_phase_current_rms_from_conduction_current(
            phase_current_conduction_a=conduction_current_a,
            control_mode=MotorControlMode.BLDC_120_DEGREE,
        ),
        expected_phase_rms_a,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        calculate_bldc_line_current_rms_from_conduction_current(
            phase_current_conduction_a=conduction_current_a,
            control_mode=MotorControlMode.BLDC_120_DEGREE,
        ),
        expected_phase_rms_a,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )


def test_bldc_phase_current_peak_is_not_inferred_from_sinusoidal_sqrt2_rule():
    conduction_current_a = 15.0
    phase_rms_a = calculate_bldc_phase_current_rms_from_conduction_current(
        phase_current_conduction_a=conduction_current_a,
        control_mode=MotorControlMode.BLDC_120_DEGREE,
    )

    assert not math.isclose(conduction_current_a, math.sqrt(2.0) * phase_rms_a, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(
        calculate_bldc_conduction_current_from_phase_rms_current(
            phase_current_rms_a=phase_rms_a,
            control_mode=MotorControlMode.BLDC_120_DEGREE,
        ),
        conduction_current_a,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
