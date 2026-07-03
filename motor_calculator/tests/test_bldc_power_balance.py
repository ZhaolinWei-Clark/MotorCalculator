"""Power-balance tests for ideal BLDC 120-degree revised semantics."""

from __future__ import annotations

import math

from motor_core import (
    MotorControlMode,
    calculate_bldc_average_electromagnetic_power_from_numeric_integration_w,
    calculate_bldc_average_electromagnetic_power_w,
)

REL_TOL = 1e-8
ABS_TOL = 1e-10


def test_bldc_average_electromagnetic_power_matches_analytic_and_numeric_results():
    phase_flat_top_back_emf_v = 24.0
    conduction_current_a = 5.0
    expected_power_w = 2.0 * phase_flat_top_back_emf_v * conduction_current_a

    actual_power_w = calculate_bldc_average_electromagnetic_power_w(
        phase_flat_top_back_emf_v=phase_flat_top_back_emf_v,
        conduction_current_a=conduction_current_a,
        control_mode=MotorControlMode.BLDC_120_DEGREE,
    )
    numeric_power_w = calculate_bldc_average_electromagnetic_power_from_numeric_integration_w(
        phase_flat_top_back_emf_v=phase_flat_top_back_emf_v,
        conduction_current_a=conduction_current_a,
        control_mode=MotorControlMode.BLDC_120_DEGREE,
    )

    assert math.isclose(actual_power_w, expected_power_w, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(numeric_power_w, expected_power_w, rel_tol=1e-6, abs_tol=1e-8)

