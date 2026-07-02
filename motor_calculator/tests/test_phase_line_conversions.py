"""Phase/line conversion semantic tests."""

from __future__ import annotations

import math

from motor_core import MotorControlMode
from motor_core.electrical_semantics import (
    sinusoidal_phase_voltage_rms_v_to_line_voltage_rms_v,
    y_connected_phase_current_rms_a_to_line_current_rms_a,
)

REL_TOL = 1e-8
ABS_TOL = 1e-10


def test_y_connection_line_current_rms_equals_phase_current_rms():
    actual = y_connected_phase_current_rms_a_to_line_current_rms_a(12.5)
    assert math.isclose(actual, 12.5, rel_tol=REL_TOL, abs_tol=ABS_TOL)


def test_sinusoidal_phase_voltage_rms_to_line_voltage_rms():
    actual = sinusoidal_phase_voltage_rms_v_to_line_voltage_rms_v(12.0, MotorControlMode.PMSM_SINUSOIDAL)
    expected = math.sqrt(3.0) * 12.0
    assert math.isclose(actual, expected, rel_tol=REL_TOL, abs_tol=ABS_TOL)
