"""Independent PMSM sinusoidal reference-case validation tests."""

from __future__ import annotations

import math

import pytest

from motor_core import (
    MotorControlMode,
    calculate_revised_pmsm_back_emf_constants_from_phase_rms_and_angular_speed,
    derive_revised_pmsm_torque_constants_from_power_balance,
)
from reference_case_builder import (
    DERIVED_FIELDS,
    EXPECTED_FIELDS,
    SUPPORTED_SOURCE_TYPES,
    build_independent_reference_values,
    load_pmsm_reference_cases,
)

REL_TOL = 1e-8
ABS_TOL = 1e-10

REQUIRED_CASE_FIELDS = {
    "case_id",
    "source_type",
    "source_description",
    "case_description_zh",
    "model_assumptions",
    "pole_pairs",
    "mechanical_speed_rpm",
    "mechanical_angular_speed_rad_s",
    "back_emf_phase_peak_v",
    "back_emf_phase_rms_v",
    "back_emf_line_rms_v",
    "phase_current_peak_a",
    "phase_current_rms_a",
    "expected_ke_phase_peak_v_per_rad_s",
    "expected_ke_phase_rms_v_per_rad_s",
    "expected_ke_line_rms_v_per_rad_s",
    "expected_ke_line_rms_v_per_krpm",
    "expected_kt_phase_peak_nm_per_a",
    "expected_kt_phase_rms_nm_per_a",
    "expected_electromagnetic_power_w",
    "expected_torque_nm",
}


def _reference_cases():
    return load_pmsm_reference_cases()


def _reference_case_ids():
    return [case["case_id"] for case in _reference_cases()]


def _assert_close(actual: float, expected: float) -> None:
    assert math.isclose(actual, expected, rel_tol=REL_TOL, abs_tol=ABS_TOL)


def test_pmsm_reference_fixture_declares_supported_sources_and_required_fields():
    cases = _reference_cases()

    assert len(cases) >= 4
    assert any(case["source_type"] == "analytical_reference" for case in cases)

    for case in cases:
        assert REQUIRED_CASE_FIELDS.issubset(case.keys())
        assert case["source_type"] in SUPPORTED_SOURCE_TYPES
        assert case["source_description"]
        assert case["case_description_zh"]
        assert case["model_assumptions"]


@pytest.mark.parametrize("case", _reference_cases(), ids=_reference_case_ids())
def test_pmsm_reference_fixture_values_match_independent_builder(case):
    independently_built = build_independent_reference_values(case)

    for field_name in DERIVED_FIELDS + EXPECTED_FIELDS:
        _assert_close(case[field_name], independently_built[field_name])


@pytest.mark.parametrize("case", _reference_cases(), ids=_reference_case_ids())
def test_revised_pmsm_ke_kt_match_independent_reference_expectations(case):
    (
        actual_ke_phase_peak_v_per_rad_s,
        actual_ke_phase_rms_v_per_rad_s,
        actual_ke_line_rms_v_per_rad_s,
        actual_ke_line_rms_v_per_krpm,
        actual_back_emf_phase_peak_v,
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

    _assert_close(actual_back_emf_phase_peak_v, case["back_emf_phase_peak_v"])
    _assert_close(actual_ke_phase_peak_v_per_rad_s, case["expected_ke_phase_peak_v_per_rad_s"])
    _assert_close(actual_ke_phase_rms_v_per_rad_s, case["expected_ke_phase_rms_v_per_rad_s"])
    _assert_close(actual_ke_line_rms_v_per_rad_s, case["expected_ke_line_rms_v_per_rad_s"])
    _assert_close(actual_ke_line_rms_v_per_krpm, case["expected_ke_line_rms_v_per_krpm"])
    _assert_close(actual_kt_phase_peak_nm_per_a, case["expected_kt_phase_peak_nm_per_a"])
    _assert_close(actual_kt_phase_rms_nm_per_a, case["expected_kt_phase_rms_nm_per_a"])
