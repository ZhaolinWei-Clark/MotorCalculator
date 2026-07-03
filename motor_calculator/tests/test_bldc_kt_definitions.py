"""Revised BLDC Kt definition tests."""

from __future__ import annotations

import math

from motor_core import (
    MotorControlMode,
    calculate_bldc_average_electromagnetic_power_w,
    calculate_bldc_phase_current_rms_from_conduction_current,
    compare_legacy_and_revised_bldc_ke_kt,
)

REL_TOL = 1e-8
ABS_TOL = 1e-10


def test_revised_bldc_kt_definitions_follow_average_power_balance():
    semantics = compare_legacy_and_revised_bldc_ke_kt(
        control_mode=MotorControlMode.BLDC_120_DEGREE,
        legacy_back_emf_phase_rms_v=16.0,
        mechanical_speed_rpm=1500.0,
        legacy_back_emf_constant_line_rms_v_per_krpm=20.0,
    )
    conduction_current_a = 7.0
    phase_current_rms_a = calculate_bldc_phase_current_rms_from_conduction_current(
        phase_current_conduction_a=conduction_current_a,
        control_mode=MotorControlMode.BLDC_120_DEGREE,
    )
    average_power_w = calculate_bldc_average_electromagnetic_power_w(
        phase_flat_top_back_emf_v=semantics.revised_bldc_phase_flat_top_back_emf_v,
        conduction_current_a=conduction_current_a,
        control_mode=MotorControlMode.BLDC_120_DEGREE,
    )
    mechanical_angular_speed_rad_s = 1500.0 * 2.0 * math.pi / 60.0
    expected_torque_nm = average_power_w / mechanical_angular_speed_rad_s

    assert math.isclose(
        semantics.revised_bldc_torque_constant_nm_per_conduction_a * conduction_current_a,
        expected_torque_nm,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        semantics.revised_bldc_torque_constant_nm_per_phase_rms_a * phase_current_rms_a,
        expected_torque_nm,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        semantics.revised_bldc_torque_constant_nm_per_conduction_a,
        2.0 * semantics.revised_bldc_back_emf_constant_phase_flat_top_v_per_rad_s,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
