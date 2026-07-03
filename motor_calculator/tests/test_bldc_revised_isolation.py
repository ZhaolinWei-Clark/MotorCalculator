"""Isolation tests ensuring revised BLDC Ke/Kt stays parallel to legacy paths."""

from __future__ import annotations

import math

from motor_core import MotorControlMode, calculate_from_legacy_params

from helpers import build_sample_legacy_params

REL_TOL = 1e-8
ABS_TOL = 1e-10


def test_bldc_analysis_exposes_revised_bldc_fields_without_replacing_legacy_outputs():
    result = calculate_from_legacy_params(build_sample_legacy_params(waveform="BLDC"))

    assert result.electrical.control_mode is MotorControlMode.BLDC_120_DEGREE
    assert result.electrical.legacy_bldc_back_emf_constant_line_rms_v_per_krpm == result.electrical.legacy_back_emf_constant_line_rms_v_per_krpm
    assert result.electrical.legacy_bldc_torque_constant_nm_per_phase_rms_a == result.electrical.legacy_torque_constant_nm_per_phase_rms_a
    assert result.electrical.revised_bldc_back_emf_constant_phase_flat_top_v_per_rad_s is not None
    assert result.electrical.revised_bldc_back_emf_constant_line_rms_v_per_krpm is not None
    assert result.electrical.revised_bldc_torque_constant_nm_per_conduction_a is not None
    assert result.electrical.revised_bldc_torque_constant_nm_per_phase_rms_a is not None
    assert result.electrical.revised_back_emf_constant_phase_peak_v_per_rad_s is None
    assert result.electrical.revised_torque_constant_nm_per_phase_rms_a is None
    assert result.performance.required_voltage_semantics_status == "legacy_line_rms_requirement_model"
    assert math.isclose(
        result.performance.phase_current_rms_a,
        result.performance.legacy_rated_torque_nm / result.electrical.legacy_torque_constant_nm_per_phase_rms_a,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )


def test_bldc_revised_semantics_do_not_change_required_voltage_or_loss_chain():
    bldc_result = calculate_from_legacy_params(build_sample_legacy_params(waveform="BLDC"))
    legacy_like_result = calculate_from_legacy_params(build_sample_legacy_params(waveform="???"))

    assert bldc_result.electrical.control_mode is MotorControlMode.BLDC_120_DEGREE
    assert legacy_like_result.electrical.control_mode is MotorControlMode.BLDC_120_DEGREE
    assert math.isclose(
        bldc_result.performance.required_voltage_v,
        legacy_like_result.performance.required_voltage_v,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        bldc_result.performance.copper_loss_w,
        legacy_like_result.performance.copper_loss_w,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
