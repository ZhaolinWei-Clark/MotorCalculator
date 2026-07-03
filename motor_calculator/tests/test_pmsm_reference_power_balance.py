"""Power-balance validation for independent PMSM sinusoidal reference cases."""

from __future__ import annotations

import math

import pytest

from motor_core import (
    MotorControlMode,
    calculate_mechanical_power_from_torque_and_speed_w,
    calculate_pmsm_three_phase_electromagnetic_power_w,
    calculate_revised_pmsm_back_emf_constants_from_phase_rms_and_angular_speed,
    derive_revised_pmsm_torque_constants_from_power_balance,
)
from reference_case_builder import build_independent_reference_values, load_pmsm_reference_cases

REL_TOL = 1e-8
ABS_TOL = 1e-10


def _reference_cases():
    return load_pmsm_reference_cases()


def _reference_case_ids():
    return [case["case_id"] for case in _reference_cases()]


def _assert_close(actual: float, expected: float) -> None:
    assert math.isclose(actual, expected, rel_tol=REL_TOL, abs_tol=ABS_TOL)


@pytest.mark.parametrize("case", _reference_cases(), ids=_reference_case_ids())
def test_independent_reference_power_balance_is_self_consistent(case):
    independently_built = build_independent_reference_values(case)

    expected_torque_from_power = independently_built["expected_electromagnetic_power_w"] / independently_built[
        "mechanical_angular_speed_rad_s"
    ]
    expected_torque_from_kt_peak = independently_built["expected_kt_phase_peak_nm_per_a"] * case["phase_current_peak_a"]
    expected_torque_from_kt_rms = independently_built["expected_kt_phase_rms_nm_per_a"] * case["phase_current_rms_a"]

    _assert_close(expected_torque_from_power, independently_built["expected_torque_nm"])
    _assert_close(expected_torque_from_kt_peak, independently_built["expected_torque_nm"])
    _assert_close(expected_torque_from_kt_rms, independently_built["expected_torque_nm"])


@pytest.mark.parametrize("case", _reference_cases(), ids=_reference_case_ids())
def test_production_pmsm_power_and_torque_match_independent_reference_cases(case):
    # These checks mirror the documented Phase 3D analytical formulas without
    # using production functions to build the expected values.
    independently_built = build_independent_reference_values(case)
    actual_power_w = calculate_pmsm_three_phase_electromagnetic_power_w(
        back_emf_phase_peak_v=case["back_emf_phase_peak_v"],
        phase_current_peak_a=case["phase_current_peak_a"],
        control_mode=MotorControlMode.PMSM_SINUSOIDAL,
    )
    (
        actual_ke_phase_peak_v_per_rad_s,
        actual_ke_phase_rms_v_per_rad_s,
        _actual_ke_line_rms_v_per_rad_s,
        _actual_ke_line_rms_v_per_krpm,
        _actual_back_emf_phase_peak_v,
    ) = calculate_revised_pmsm_back_emf_constants_from_phase_rms_and_angular_speed(
        back_emf_phase_rms_v=case["back_emf_phase_rms_v"],
        mechanical_speed_rpm=case["mechanical_speed_rpm"],
        mechanical_angular_speed_rad_s=case["mechanical_angular_speed_rad_s"],
        control_mode=MotorControlMode.PMSM_SINUSOIDAL,
    )
    actual_kt_phase_peak_nm_per_a, actual_kt_phase_rms_nm_per_a = derive_revised_pmsm_torque_constants_from_power_balance(
        revised_back_emf_constant_phase_peak_v_per_rad_s=actual_ke_phase_peak_v_per_rad_s,
        revised_back_emf_constant_phase_rms_v_per_rad_s=actual_ke_phase_rms_v_per_rad_s,
        control_mode=MotorControlMode.PMSM_SINUSOIDAL,
    )

    actual_torque_from_power = actual_power_w / case["mechanical_angular_speed_rad_s"]
    actual_torque_from_kt_peak = actual_kt_phase_peak_nm_per_a * case["phase_current_peak_a"]
    actual_torque_from_kt_rms = actual_kt_phase_rms_nm_per_a * case["phase_current_rms_a"]
    actual_mechanical_power_w = calculate_mechanical_power_from_torque_and_speed_w(
        torque_nm=case["expected_torque_nm"],
        mechanical_angular_speed_rad_s=case["mechanical_angular_speed_rad_s"],
    )

    _assert_close(actual_power_w, case["expected_electromagnetic_power_w"])
    _assert_close(actual_torque_from_power, case["expected_torque_nm"])
    _assert_close(actual_torque_from_kt_peak, case["expected_torque_nm"])
    _assert_close(actual_torque_from_kt_rms, case["expected_torque_nm"])
    _assert_close(actual_mechanical_power_w, independently_built["expected_electromagnetic_power_w"])
