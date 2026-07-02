"""Speed, pole, and frequency semantic tests."""

from __future__ import annotations

import math

from motor_core.electrical_semantics import (
    mechanical_angular_speed_rad_s_to_electrical_angular_speed_rad_s,
    mechanical_speed_rpm_to_electrical_frequency_hz,
    mechanical_speed_rpm_to_mechanical_angular_speed_rad_s,
    pole_pairs_to_pole_count,
)

REL_TOL = 1e-8
ABS_TOL = 1e-10


def test_pole_count_is_twice_pole_pairs():
    assert pole_pairs_to_pole_count(8) == 16


def test_mechanical_speed_rpm_to_mechanical_angular_speed_rad_s():
    actual = mechanical_speed_rpm_to_mechanical_angular_speed_rad_s(3000.0)
    expected = 3000.0 * 2.0 * math.pi / 60.0
    assert math.isclose(actual, expected, rel_tol=REL_TOL, abs_tol=ABS_TOL)


def test_mechanical_speed_rpm_to_electrical_frequency_hz():
    actual = mechanical_speed_rpm_to_electrical_frequency_hz(2500.0, 8)
    expected = 2500.0 * 8 / 60.0
    assert math.isclose(actual, expected, rel_tol=REL_TOL, abs_tol=ABS_TOL)


def test_mechanical_angular_speed_rad_s_to_electrical_angular_speed_rad_s():
    mechanical_angular_speed_rad_s = mechanical_speed_rpm_to_mechanical_angular_speed_rad_s(2500.0)
    actual = mechanical_angular_speed_rad_s_to_electrical_angular_speed_rad_s(mechanical_angular_speed_rad_s, 8)
    expected = mechanical_angular_speed_rad_s * 8
    assert math.isclose(actual, expected, rel_tol=REL_TOL, abs_tol=ABS_TOL)
