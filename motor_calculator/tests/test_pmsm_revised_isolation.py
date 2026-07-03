"""Isolation tests ensuring revised PMSM Ke/Kt does not affect legacy downstream paths."""

from __future__ import annotations

import inspect
import math

from motor_core import MotorControlMode, MotorAnalysisEngine, calculate_from_legacy_params

from helpers import build_sample_legacy_params

REL_TOL = 1e-8
ABS_TOL = 1e-10


def test_revised_pmsm_ke_kt_does_not_replace_legacy_downstream_outputs():
    result = calculate_from_legacy_params(build_sample_legacy_params())

    assert result.electrical.control_mode is MotorControlMode.PMSM_SINUSOIDAL
    assert math.isclose(
        result.performance.phase_current_rms_a,
        result.performance.legacy_rated_torque_nm / result.electrical.legacy_torque_constant_nm_per_phase_rms_a,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert result.performance.required_voltage_semantics_status == "legacy_line_rms_requirement_model"
    assert result.electrical.legacy_back_emf_constant_line_rms_v_per_krpm == result.electrical.Ke
    assert result.electrical.legacy_torque_constant_nm_per_phase_rms_a == result.electrical.Kt


def test_revised_pmsm_ke_kt_is_not_used_in_run_full_analysis_downstream_chain():
    source = inspect.getsource(MotorAnalysisEngine.run_full_analysis)

    assert "legacy_torque_constant_nm_per_phase_rms_a" in source
    assert "revised_torque_constant_nm_per_phase_rms_a" not in source
    assert "revised_back_emf_constant_line_rms_v_per_rad_s" not in source
    assert "required_voltage_v = sqrt(" in source


def test_bldc_analysis_keeps_revised_pmsm_fields_disabled():
    result = calculate_from_legacy_params(build_sample_legacy_params(waveform="æ¢¯å½¢æ³¢"))

    assert result.electrical.control_mode is MotorControlMode.BLDC_120_DEGREE
    assert result.electrical.revised_back_emf_constant_phase_peak_v_per_rad_s is None
    assert result.electrical.revised_back_emf_constant_phase_rms_v_per_rad_s is None
    assert result.electrical.revised_back_emf_constant_line_rms_v_per_rad_s is None
    assert result.electrical.revised_back_emf_constant_line_rms_v_per_krpm is None
    assert result.electrical.revised_torque_constant_nm_per_phase_peak_a is None
    assert result.electrical.revised_torque_constant_nm_per_phase_rms_a is None
    assert result.electrical.pmsm_power_consistency_status == "not_applicable_bldc_legacy_provisional"
