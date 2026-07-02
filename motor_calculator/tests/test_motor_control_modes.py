"""Motor control mode boundary tests."""

from __future__ import annotations

import pytest

from motor_core import MotorControlMode, MotorSemanticsError, calculate_from_legacy_params, legacy_params_to_model_input
from motor_core.electrical_semantics import normalize_motor_control_mode

from helpers import build_sample_legacy_params


def test_legacy_waveform_maps_to_explicit_pmsm_mode():
    motor_input = legacy_params_to_model_input(build_sample_legacy_params(waveform="正弦波"))
    assert motor_input.control_mode is MotorControlMode.PMSM_SINUSOIDAL


def test_unknown_legacy_waveform_falls_back_to_legacy_bldc_branch():
    motor_input = legacy_params_to_model_input(build_sample_legacy_params(waveform="???"))
    assert motor_input.control_mode is MotorControlMode.BLDC_120_DEGREE


def test_invalid_explicit_mode_raises_clear_exception():
    with pytest.raises(MotorSemanticsError):
        normalize_motor_control_mode("invalid_mode")


def test_bldc_analysis_marks_peak_quantities_provisional():
    result = calculate_from_legacy_params(build_sample_legacy_params(waveform="梯形波"))
    assert result.electrical.control_mode is MotorControlMode.BLDC_120_DEGREE
    assert result.electrical.back_emf_phase_peak_v is None
    assert result.performance.phase_current_peak_a is None
    assert result.electrical.legacy_control_model_name == "legacy_bldc_model"
    assert "provisional" in result.electrical.kt_semantics_status
