"""Ke/Kt unit semantic tests."""

from __future__ import annotations

import math

from motor_core import MotorControlMode, calculate_from_legacy_params
from motor_core.electrical_semantics import line_rms_v_per_krpm_to_line_rms_v_per_rad_s

from helpers import build_sample_legacy_params

REL_TOL = 1e-8
ABS_TOL = 1e-10


def test_line_rms_v_per_krpm_to_line_rms_v_per_rad_s_conversion():
    actual = line_rms_v_per_krpm_to_line_rms_v_per_rad_s(14.733169889368446)
    expected = 14.733169889368446 / (1000.0 * 2.0 * math.pi / 60.0)
    assert math.isclose(actual, expected, rel_tol=REL_TOL, abs_tol=ABS_TOL)


def test_pmsm_analysis_exposes_explicit_ke_kt_units_without_overwriting_legacy_fields():
    result = calculate_from_legacy_params(build_sample_legacy_params(waveform="正弦波"))
    assert result.electrical.control_mode is MotorControlMode.PMSM_SINUSOIDAL
    assert result.electrical.legacy_back_emf_constant_line_rms_v_per_krpm == result.electrical.Ke
    assert result.electrical.legacy_torque_constant_nm_per_phase_rms_a == result.electrical.Kt
    assert result.electrical.back_emf_constant_line_rms_v_per_rad_s is not None
    assert result.electrical.back_emf_constant_phase_rms_v_per_rad_s is not None
    assert result.electrical.torque_constant_nm_per_phase_peak_a is not None
    assert result.electrical.torque_constant_nm_per_phase_rms_a is not None
