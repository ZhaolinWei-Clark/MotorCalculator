"""Independent BLDC analytical reference-case validation tests."""

from __future__ import annotations

import math

import pytest

from motor_core import (
    MotorControlMode,
    calculate_bldc_average_electromagnetic_power_w,
    compare_legacy_and_revised_bldc_ke_kt,
)
from bldc_reference_case_builder import (
    DERIVED_FIELDS,
    EXPECTED_FIELDS,
    SUPPORTED_SOURCE_TYPES,
    build_independent_bldc_reference_values,
    load_bldc_reference_cases,
)

REL_TOL = 1e-8
ABS_TOL = 1e-10
NUMERIC_REL_TOL = 1e-6
NUMERIC_ABS_TOL = 1e-8

REQUIRED_CASE_FIELDS = {
    "case_id",
    "source_type",
    "source_description",
    "case_description_zh",
    "model_assumptions",
    "pole_pairs",
    "mechanical_speed_rpm",
    "mechanical_angular_speed_rad_s",
    "phase_flat_top_back_emf_v",
    "phase_peak_back_emf_v",
    "conduction_current_a",
    "expected_phase_back_emf_rms_v",
    "expected_line_to_line_peak_back_emf_v",
    "expected_line_back_emf_rms_v",
    "expected_phase_current_rms_a",
    "expected_ke_phase_flat_top_v_per_rad_s",
    "expected_ke_phase_peak_v_per_rad_s",
    "expected_ke_phase_rms_v_per_rad_s",
    "expected_ke_line_rms_v_per_rad_s",
    "expected_ke_line_rms_v_per_krpm",
    "expected_kt_conduction_nm_per_a",
    "expected_kt_phase_rms_nm_per_a",
    "expected_average_electromagnetic_power_w",
    "expected_torque_nm",
    "numeric_phase_back_emf_rms_v",
    "numeric_line_back_emf_rms_v",
    "numeric_phase_current_rms_a",
    "numeric_average_electromagnetic_power_w",
}


def _reference_cases():
    return load_bldc_reference_cases()


def _reference_case_ids():
    return [case["case_id"] for case in _reference_cases()]


def _assert_close(actual: float, expected: float, *, rel_tol: float = REL_TOL, abs_tol: float = ABS_TOL) -> None:
    assert math.isclose(actual, expected, rel_tol=rel_tol, abs_tol=abs_tol)


def test_bldc_reference_fixture_declares_supported_sources_and_required_fields():
    cases = _reference_cases()

    assert len(cases) >= 4
    assert all(case["source_type"] == "analytical_reference" for case in cases)

    for case in cases:
        assert REQUIRED_CASE_FIELDS.issubset(case.keys())
        assert case["source_type"] in SUPPORTED_SOURCE_TYPES
        assert case["source_description"]
        assert case["case_description_zh"]
        assert case["model_assumptions"]


@pytest.mark.parametrize("case", _reference_cases(), ids=_reference_case_ids())
def test_bldc_reference_fixture_values_match_independent_builder(case):
    independently_built = build_independent_bldc_reference_values(case)

    for field_name in DERIVED_FIELDS + EXPECTED_FIELDS:
        rel_tol = NUMERIC_REL_TOL if field_name.startswith("numeric_") else REL_TOL
        abs_tol = NUMERIC_ABS_TOL if field_name.startswith("numeric_") else ABS_TOL
        _assert_close(case[field_name], independently_built[field_name], rel_tol=rel_tol, abs_tol=abs_tol)


@pytest.mark.parametrize("case", _reference_cases(), ids=_reference_case_ids())
def test_revised_bldc_ke_kt_match_independent_reference_expectations(case):
    semantics = compare_legacy_and_revised_bldc_ke_kt(
        control_mode=MotorControlMode.BLDC_120_DEGREE,
        legacy_back_emf_phase_rms_v=case["expected_phase_back_emf_rms_v"],
        mechanical_speed_rpm=case["mechanical_speed_rpm"],
        legacy_back_emf_constant_line_rms_v_per_krpm=case["expected_ke_line_rms_v_per_krpm"],
    )
    actual_average_power_w = calculate_bldc_average_electromagnetic_power_w(
        phase_flat_top_back_emf_v=semantics.revised_bldc_phase_flat_top_back_emf_v,
        conduction_current_a=case["conduction_current_a"],
        control_mode=MotorControlMode.BLDC_120_DEGREE,
    )
    actual_torque_nm = actual_average_power_w / case["mechanical_angular_speed_rad_s"]

    _assert_close(semantics.revised_bldc_phase_flat_top_back_emf_v, case["phase_flat_top_back_emf_v"])
    _assert_close(semantics.revised_bldc_phase_peak_back_emf_v, case["phase_peak_back_emf_v"])
    _assert_close(semantics.revised_bldc_phase_rms_back_emf_v, case["expected_phase_back_emf_rms_v"])
    _assert_close(semantics.revised_bldc_line_to_line_peak_back_emf_v, case["expected_line_to_line_peak_back_emf_v"])
    _assert_close(semantics.revised_bldc_line_to_line_rms_back_emf_v, case["expected_line_back_emf_rms_v"])
    _assert_close(semantics.revised_bldc_back_emf_constant_phase_flat_top_v_per_rad_s, case["expected_ke_phase_flat_top_v_per_rad_s"])
    _assert_close(semantics.revised_bldc_back_emf_constant_phase_peak_v_per_rad_s, case["expected_ke_phase_peak_v_per_rad_s"])
    _assert_close(semantics.revised_bldc_back_emf_constant_phase_rms_v_per_rad_s, case["expected_ke_phase_rms_v_per_rad_s"])
    _assert_close(semantics.revised_bldc_back_emf_constant_line_rms_v_per_rad_s, case["expected_ke_line_rms_v_per_rad_s"])
    _assert_close(semantics.revised_bldc_back_emf_constant_line_rms_v_per_krpm, case["expected_ke_line_rms_v_per_krpm"])
    _assert_close(semantics.revised_bldc_torque_constant_nm_per_conduction_a, case["expected_kt_conduction_nm_per_a"])
    _assert_close(semantics.revised_bldc_torque_constant_nm_per_phase_rms_a, case["expected_kt_phase_rms_nm_per_a"])
    _assert_close(actual_average_power_w, case["expected_average_electromagnetic_power_w"])
    _assert_close(actual_torque_nm, case["expected_torque_nm"])
