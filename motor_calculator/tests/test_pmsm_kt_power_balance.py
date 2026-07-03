"""PMSM torque-constant power-balance tests."""

from __future__ import annotations

import math

import pytest

from motor_core import (
    MotorCalculationError,
    MotorControlMode,
    MotorSemanticsError,
    calculate_mechanical_power_from_torque_and_speed_w,
    calculate_pmsm_three_phase_electromagnetic_power_w,
    derive_revised_pmsm_torque_constants_from_power_balance,
)
from motor_core.electrical_semantics import sinusoidal_phase_current_peak_a_to_phase_current_rms_a

REL_TOL = 1e-8
ABS_TOL = 1e-10


def test_revised_pmsm_kt_derivation_matches_power_balance():
    revised_back_emf_constant_phase_rms_v_per_rad_s = 0.082
    revised_back_emf_constant_phase_peak_v_per_rad_s = math.sqrt(2.0) * revised_back_emf_constant_phase_rms_v_per_rad_s
    revised_torque_constant_nm_per_phase_peak_a, revised_torque_constant_nm_per_phase_rms_a = (
        derive_revised_pmsm_torque_constants_from_power_balance(
            revised_back_emf_constant_phase_peak_v_per_rad_s=revised_back_emf_constant_phase_peak_v_per_rad_s,
            revised_back_emf_constant_phase_rms_v_per_rad_s=revised_back_emf_constant_phase_rms_v_per_rad_s,
            control_mode=MotorControlMode.PMSM_SINUSOIDAL,
        )
    )

    mechanical_angular_speed_rad_s = 314.1592653589793
    phase_current_peak_a = 6.0
    phase_current_rms_a = sinusoidal_phase_current_peak_a_to_phase_current_rms_a(
        phase_current_peak_a,
        MotorControlMode.PMSM_SINUSOIDAL,
    )
    back_emf_phase_peak_v = revised_back_emf_constant_phase_peak_v_per_rad_s * mechanical_angular_speed_rad_s

    electromagnetic_power_w = calculate_pmsm_three_phase_electromagnetic_power_w(
        back_emf_phase_peak_v=back_emf_phase_peak_v,
        phase_current_peak_a=phase_current_peak_a,
        control_mode=MotorControlMode.PMSM_SINUSOIDAL,
    )
    torque_nm = revised_torque_constant_nm_per_phase_peak_a * phase_current_peak_a
    mechanical_power_w = calculate_mechanical_power_from_torque_and_speed_w(
        torque_nm=torque_nm,
        mechanical_angular_speed_rad_s=mechanical_angular_speed_rad_s,
    )

    assert math.isclose(
        electromagnetic_power_w,
        1.5 * back_emf_phase_peak_v * phase_current_peak_a,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(mechanical_power_w, torque_nm * mechanical_angular_speed_rad_s, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(electromagnetic_power_w, mechanical_power_w, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(
        revised_torque_constant_nm_per_phase_peak_a,
        1.5 * revised_back_emf_constant_phase_peak_v_per_rad_s,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        revised_torque_constant_nm_per_phase_rms_a,
        math.sqrt(2.0) * revised_torque_constant_nm_per_phase_peak_a,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        revised_torque_constant_nm_per_phase_rms_a,
        3.0 * revised_back_emf_constant_phase_rms_v_per_rad_s,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        torque_nm,
        revised_torque_constant_nm_per_phase_rms_a * phase_current_rms_a,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )


def test_revised_pmsm_kt_derivation_rejects_bldc_mode():
    with pytest.raises(MotorSemanticsError):
        derive_revised_pmsm_torque_constants_from_power_balance(
            revised_back_emf_constant_phase_peak_v_per_rad_s=0.1,
            revised_back_emf_constant_phase_rms_v_per_rad_s=0.1 / math.sqrt(2.0),
            control_mode=MotorControlMode.BLDC_120_DEGREE,
        )


@pytest.mark.parametrize(
    ("revised_back_emf_constant_phase_peak_v_per_rad_s", "revised_back_emf_constant_phase_rms_v_per_rad_s"),
    [
        (0.0, 0.1),
        (-1.0, 0.1),
        (0.1, 0.0),
        (0.1, -1.0),
        (math.nan, 0.1),
        (math.inf, 0.1),
        (0.1, math.nan),
        (0.1, math.inf),
    ],
)
def test_revised_pmsm_kt_derivation_rejects_invalid_inputs(
    revised_back_emf_constant_phase_peak_v_per_rad_s: float,
    revised_back_emf_constant_phase_rms_v_per_rad_s: float,
):
    with pytest.raises(MotorCalculationError):
        derive_revised_pmsm_torque_constants_from_power_balance(
            revised_back_emf_constant_phase_peak_v_per_rad_s=revised_back_emf_constant_phase_peak_v_per_rad_s,
            revised_back_emf_constant_phase_rms_v_per_rad_s=revised_back_emf_constant_phase_rms_v_per_rad_s,
            control_mode=MotorControlMode.PMSM_SINUSOIDAL,
        )
