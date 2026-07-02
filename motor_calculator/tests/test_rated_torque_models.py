"""Tests for legacy and strict-SI rated torque comparison models."""

from __future__ import annotations

import inspect
import math

import pytest

from motor_core import (
    MotorCalculationError,
    calculate_from_legacy_params,
    calculate_legacy_rated_torque_nm,
    calculate_revised_rated_torque_nm,
    compare_rated_torque_models,
)
from motor_core.electrical_semantics import mechanical_speed_rpm_to_mechanical_angular_speed_rad_s
from motor_core.rated_torque_models import calculate_revised_rated_torque_nm as revised_function_source_target

from helpers import build_sample_legacy_params

REL_TOL = 1e-8
ABS_TOL = 1e-10


@pytest.mark.parametrize(
    ("rated_power_w", "mechanical_speed_rpm"),
    [
        (1000.0, 1000.0),
        (5000.0, 3000.0),
        (100.0, 100.0),
        (10000.0, 12000.0),
    ],
)
def test_rated_torque_models_match_expected_math(rated_power_w: float, mechanical_speed_rpm: float):
    mechanical_angular_speed_rad_s = mechanical_speed_rpm_to_mechanical_angular_speed_rad_s(mechanical_speed_rpm)
    legacy_rated_torque_nm = calculate_legacy_rated_torque_nm(rated_power_w, mechanical_speed_rpm)
    revised_rated_torque_nm = calculate_revised_rated_torque_nm(rated_power_w, mechanical_speed_rpm)
    comparison = compare_rated_torque_models(rated_power_w, mechanical_speed_rpm)

    assert math.isclose(
        mechanical_angular_speed_rad_s,
        mechanical_speed_rpm * 2.0 * math.pi / 60.0,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        revised_rated_torque_nm,
        rated_power_w / mechanical_angular_speed_rad_s,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        rated_power_w,
        revised_rated_torque_nm * mechanical_angular_speed_rad_s,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(comparison.legacy_rated_torque_nm, legacy_rated_torque_nm, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(comparison.revised_rated_torque_nm, revised_rated_torque_nm, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    assert math.isclose(
        comparison.rated_torque_absolute_difference_nm,
        abs(legacy_rated_torque_nm - revised_rated_torque_nm),
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert math.isclose(
        comparison.rated_torque_relative_difference,
        abs(legacy_rated_torque_nm - revised_rated_torque_nm) / revised_rated_torque_nm,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )


def test_revised_rated_torque_formula_does_not_use_legacy_approximation_constant():
    source = inspect.getsource(revised_function_source_target)
    assert "9.55" not in source
    assert "LEGACY_POWER_SPEED_TO_TORQUE_FACTOR" not in source


@pytest.mark.parametrize(
    ("rated_power_w", "mechanical_speed_rpm"),
    [
        (0.0, 1000.0),
        (-1.0, 1000.0),
        (1000.0, 0.0),
        (1000.0, -1.0),
    ],
)
def test_invalid_rated_torque_inputs_raise_clear_exceptions(rated_power_w: float, mechanical_speed_rpm: float):
    with pytest.raises(MotorCalculationError):
        calculate_legacy_rated_torque_nm(rated_power_w, mechanical_speed_rpm)
    with pytest.raises(MotorCalculationError):
        calculate_revised_rated_torque_nm(rated_power_w, mechanical_speed_rpm)


def test_phase3b_exposes_comparison_fields_without_changing_downstream_legacy_outputs():
    result = calculate_from_legacy_params(build_sample_legacy_params())

    assert math.isclose(
        result.performance.rated_torque_nm,
        result.performance.legacy_rated_torque_nm,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert result.performance.revised_rated_torque_nm != result.performance.legacy_rated_torque_nm
    assert result.performance.rated_torque_model_status == "strict_si_comparison_available"
    assert math.isclose(
        result.performance.phase_current_rms_a,
        result.performance.legacy_rated_torque_nm / result.electrical.legacy_torque_constant_nm_per_phase_rms_a,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
