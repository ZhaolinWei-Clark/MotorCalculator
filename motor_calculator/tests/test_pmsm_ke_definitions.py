"""Revised PMSM back-EMF constant definition tests."""

from __future__ import annotations

import math

import pytest

from motor_core import (
    MotorCalculationError,
    MotorControlMode,
    MotorSemanticsError,
    calculate_revised_pmsm_back_emf_constants_from_phase_rms_and_angular_speed,
    calculate_revised_pmsm_back_emf_constants_from_phase_rms_and_speed,
)
from motor_core.electrical_semantics import (
    line_rms_v_per_rad_s_to_line_rms_v_per_krpm,
    mechanical_speed_rpm_to_mechanical_angular_speed_rad_s,
    sinusoidal_phase_voltage_rms_v_to_line_voltage_rms_v,
    sinusoidal_phase_voltage_rms_v_to_phase_voltage_peak_v,
)

REL_TOL = 1e-8
ABS_TOL = 1e-10


def test_revised_pmsm_ke_definitions_follow_explicit_phase_line_units():
    back_emf_phase_rms_v = 12.5
    mechanical_speed_rpm = 1500.0
    mechanical_angular_speed_rad_s = mechanical_speed_rpm_to_mechanical_angular_speed_rad_s(mechanical_speed_rpm)
    (
        revised_back_emf_constant_phase_peak_v_per_rad_s,
        revised_back_emf_constant_phase_rms_v_per_rad_s,
        revised_back_emf_constant_line_rms_v_per_rad_s,
        revised_back_emf_constant_line_rms_v_per_krpm,
        back_emf_phase_peak_v,
    ) = calculate_revised_pmsm_back_emf_constants_from_phase_rms_and_speed(
        back_emf_phase_rms_v=back_emf_phase_rms_v,
        mechanical_speed_rpm=mechanical_speed_rpm,
        control_mode=MotorControlMode.PMSM_SINUSOIDAL,
    )

    expected_back_emf_phase_peak_v = sinusoidal_phase_voltage_rms_v_to_phase_voltage_peak_v(
        back_emf_phase_rms_v,
        MotorControlMode.PMSM_SINUSOIDAL,
    )
    expected_back_emf_line_rms_v = sinusoidal_phase_voltage_rms_v_to_line_voltage_rms_v(
        back_emf_phase_rms_v,
        MotorControlMode.PMSM_SINUSOIDAL,
    )

    assert math.isclose(back_emf_phase_peak_v, expected_back_emf_phase_peak_v, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(
        revised_back_emf_constant_phase_peak_v_per_rad_s,
        expected_back_emf_phase_peak_v / mechanical_angular_speed_rad_s,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        revised_back_emf_constant_phase_rms_v_per_rad_s,
        back_emf_phase_rms_v / mechanical_angular_speed_rad_s,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        revised_back_emf_constant_line_rms_v_per_rad_s,
        expected_back_emf_line_rms_v / mechanical_angular_speed_rad_s,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        revised_back_emf_constant_line_rms_v_per_krpm,
        expected_back_emf_line_rms_v / (mechanical_speed_rpm / 1000.0),
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        revised_back_emf_constant_line_rms_v_per_krpm,
        line_rms_v_per_rad_s_to_line_rms_v_per_krpm(revised_back_emf_constant_line_rms_v_per_rad_s),
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )


def test_revised_pmsm_ke_definitions_reject_bldc_mode():
    with pytest.raises(MotorSemanticsError):
        calculate_revised_pmsm_back_emf_constants_from_phase_rms_and_speed(
            back_emf_phase_rms_v=12.5,
            mechanical_speed_rpm=1500.0,
            control_mode=MotorControlMode.BLDC_120_DEGREE,
        )


@pytest.mark.parametrize(
    ("back_emf_phase_rms_v", "mechanical_speed_rpm"),
    [
        (0.0, 1500.0),
        (-1.0, 1500.0),
        (12.5, 0.0),
        (12.5, -1.0),
        (math.nan, 1500.0),
        (math.inf, 1500.0),
        (12.5, math.nan),
        (12.5, math.inf),
    ],
)
def test_revised_pmsm_ke_definitions_reject_invalid_phase_rms_or_speed(
    back_emf_phase_rms_v: float,
    mechanical_speed_rpm: float,
):
    with pytest.raises(MotorCalculationError):
        calculate_revised_pmsm_back_emf_constants_from_phase_rms_and_speed(
            back_emf_phase_rms_v=back_emf_phase_rms_v,
            mechanical_speed_rpm=mechanical_speed_rpm,
            control_mode=MotorControlMode.PMSM_SINUSOIDAL,
        )


@pytest.mark.parametrize("mechanical_angular_speed_rad_s", [0.0, -1.0, math.nan, math.inf])
def test_revised_pmsm_ke_definitions_reject_invalid_mechanical_angular_speed(
    mechanical_angular_speed_rad_s: float,
):
    with pytest.raises(MotorCalculationError):
        calculate_revised_pmsm_back_emf_constants_from_phase_rms_and_angular_speed(
            back_emf_phase_rms_v=12.5,
            mechanical_speed_rpm=1500.0,
            mechanical_angular_speed_rad_s=mechanical_angular_speed_rad_s,
            control_mode=MotorControlMode.PMSM_SINUSOIDAL,
        )
