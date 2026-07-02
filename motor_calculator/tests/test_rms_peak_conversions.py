"""RMS/peak conversion semantic tests."""

from __future__ import annotations

import math

import pytest

from motor_core import MotorControlMode, MotorSemanticsError
from motor_core.electrical_semantics import (
    sinusoidal_line_voltage_rms_v_to_line_voltage_peak_v,
    sinusoidal_phase_current_rms_a_to_phase_current_peak_a,
    sinusoidal_phase_voltage_rms_v_to_phase_voltage_peak_v,
)

REL_TOL = 1e-8
ABS_TOL = 1e-10


def test_sinusoidal_phase_voltage_rms_to_phase_voltage_peak():
    actual = sinusoidal_phase_voltage_rms_v_to_phase_voltage_peak_v(24.0, MotorControlMode.PMSM_SINUSOIDAL)
    expected = math.sqrt(2.0) * 24.0
    assert math.isclose(actual, expected, rel_tol=REL_TOL, abs_tol=ABS_TOL)


def test_sinusoidal_line_voltage_rms_to_line_voltage_peak():
    actual = sinusoidal_line_voltage_rms_v_to_line_voltage_peak_v(36.0, MotorControlMode.PMSM_SINUSOIDAL)
    expected = math.sqrt(2.0) * 36.0
    assert math.isclose(actual, expected, rel_tol=REL_TOL, abs_tol=ABS_TOL)


def test_sinusoidal_phase_current_rms_to_phase_current_peak():
    actual = sinusoidal_phase_current_rms_a_to_phase_current_peak_a(10.0, MotorControlMode.PMSM_SINUSOIDAL)
    expected = math.sqrt(2.0) * 10.0
    assert math.isclose(actual, expected, rel_tol=REL_TOL, abs_tol=ABS_TOL)


def test_bldc_mode_rejects_sinusoidal_peak_conversion():
    with pytest.raises(MotorSemanticsError):
        sinusoidal_phase_voltage_rms_v_to_phase_voltage_peak_v(24.0, MotorControlMode.BLDC_120_DEGREE)
