"""Independence checks for BLDC analytical reference validation."""

from __future__ import annotations

import hashlib
import inspect
import math
from pathlib import Path

from motor_core import MotorControlMode, calculate_from_legacy_params
from bldc_reference_case_builder import FIXTURE_PATH, build_independent_bldc_reference_values, load_bldc_reference_cases

from helpers import build_sample_legacy_params
import bldc_reference_case_builder

REL_TOL = 1e-8
ABS_TOL = 1e-10
NUMERIC_REL_TOL = 1e-6
NUMERIC_ABS_TOL = 1e-8
LEGACY_BASELINE_SHA256 = "15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9"


def test_bldc_reference_case_builder_does_not_import_production_modules():
    source = inspect.getsource(bldc_reference_case_builder)

    assert "motor_core" not in source
    assert "bldc_ke_kt_models" not in source
    assert "electrical_semantics" not in source
    assert "calculations" not in source
    assert "compare_legacy_and_revised_bldc_ke_kt" not in source
    assert "calculate_bldc_" not in source


def test_bldc_reference_fixture_expected_values_are_rebuilt_from_fixture_primitives():
    for case in load_bldc_reference_cases():
        independently_built = build_independent_bldc_reference_values(case)
        for field_name, expected_value in independently_built.items():
            rel_tol = NUMERIC_REL_TOL if field_name.startswith("numeric_") else REL_TOL
            abs_tol = NUMERIC_ABS_TOL if field_name.startswith("numeric_") else ABS_TOL
            assert math.isclose(case[field_name], expected_value, rel_tol=rel_tol, abs_tol=abs_tol)


def test_bldc_reference_validation_keeps_legacy_baseline_fixture_hash_unchanged():
    legacy_baseline_path = Path(__file__).resolve().parent / "fixtures" / "legacy_baseline.json"
    current_hash = hashlib.sha256(legacy_baseline_path.read_bytes()).hexdigest()

    assert current_hash == LEGACY_BASELINE_SHA256
    assert FIXTURE_PATH.name == "bldc_reference_cases.json"


def test_bldc_reference_validation_keeps_legacy_downstream_defaults():
    result = calculate_from_legacy_params(build_sample_legacy_params(waveform="BLDC"))

    assert result.electrical.control_mode is MotorControlMode.BLDC_120_DEGREE
    assert result.electrical.revised_bldc_torque_constant_nm_per_phase_rms_a is not None
    assert result.electrical.bldc_power_balance_status == "validated_from_piecewise_and_numeric_integration"
    assert math.isclose(
        result.performance.phase_current_rms_a,
        result.performance.legacy_rated_torque_nm / result.electrical.legacy_torque_constant_nm_per_phase_rms_a,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    )
    assert result.performance.required_voltage_semantics_status == "legacy_line_rms_requirement_model"
