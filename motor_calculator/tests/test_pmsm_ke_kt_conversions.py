"""PMSM revised Ke/Kt output conversion tests."""

from __future__ import annotations

import math

from motor_core import MotorControlMode, calculate_from_legacy_params
from motor_core.electrical_semantics import line_rms_v_per_rad_s_to_line_rms_v_per_krpm

from helpers import build_sample_legacy_params

REL_TOL = 1e-8
ABS_TOL = 1e-10


def test_pmsm_analysis_exposes_revised_ke_kt_fields_with_compatible_comparisons():
    result = calculate_from_legacy_params(build_sample_legacy_params())

    assert result.electrical.control_mode is MotorControlMode.PMSM_SINUSOIDAL
    assert result.electrical.revised_back_emf_constant_phase_peak_v_per_rad_s is not None
    assert result.electrical.revised_back_emf_constant_phase_rms_v_per_rad_s is not None
    assert result.electrical.revised_back_emf_constant_line_rms_v_per_rad_s is not None
    assert result.electrical.revised_back_emf_constant_line_rms_v_per_krpm is not None
    assert result.electrical.revised_torque_constant_nm_per_phase_peak_a is not None
    assert result.electrical.revised_torque_constant_nm_per_phase_rms_a is not None

    assert math.isclose(
        result.electrical.back_emf_constant_phase_peak_v_per_rad_s,
        result.electrical.revised_back_emf_constant_phase_peak_v_per_rad_s,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        result.electrical.back_emf_constant_phase_rms_v_per_rad_s,
        result.electrical.revised_back_emf_constant_phase_rms_v_per_rad_s,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        result.electrical.back_emf_constant_line_rms_v_per_rad_s,
        result.electrical.revised_back_emf_constant_line_rms_v_per_rad_s,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        result.electrical.back_emf_constant_line_rms_v_per_krpm,
        result.electrical.revised_back_emf_constant_line_rms_v_per_krpm,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        result.electrical.torque_constant_nm_per_phase_peak_a,
        result.electrical.revised_torque_constant_nm_per_phase_peak_a,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        result.electrical.torque_constant_nm_per_phase_rms_a,
        result.electrical.revised_torque_constant_nm_per_phase_rms_a,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        result.electrical.revised_back_emf_constant_line_rms_v_per_krpm,
        line_rms_v_per_rad_s_to_line_rms_v_per_krpm(result.electrical.revised_back_emf_constant_line_rms_v_per_rad_s),
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(result.electrical.ke_legacy_revised_relative_difference, 0.0, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(result.electrical.kt_legacy_revised_relative_difference, 0.0, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert result.electrical.ke_model_status == "pmsm_sinusoidal_mechanical_speed_basis"
    assert result.electrical.kt_model_status == "pmsm_sinusoidal_power_balance_derived"
    assert result.electrical.pmsm_power_consistency_status == "validated_from_three_phase_power_balance"
