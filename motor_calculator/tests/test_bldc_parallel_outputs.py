"""Parallel-output validation for legacy BLDC baseline cases."""

from __future__ import annotations

import json
import math
from pathlib import Path

from motor_core import MotorControlMode, calculate_from_legacy_params

REL_TOL = 1e-8
ABS_TOL = 1e-10


def _load_legacy_baseline_cases():
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "legacy_baseline.json"
    with fixture_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)["cases"]


def test_legacy_baseline_cases_keep_parallel_bldc_outputs_without_changing_defaults():
    for case in _load_legacy_baseline_cases():
        result = calculate_from_legacy_params(case["legacy_inputs"])

        assert result.electrical.control_mode is MotorControlMode.BLDC_120_DEGREE
        assert result.electrical.legacy_bldc_back_emf_constant_line_rms_v_per_krpm == result.electrical.Ke
        assert result.electrical.legacy_bldc_torque_constant_nm_per_phase_rms_a == result.electrical.Kt
        assert result.electrical.revised_bldc_back_emf_constant_phase_flat_top_v_per_rad_s is not None
        assert result.electrical.revised_bldc_back_emf_constant_line_rms_v_per_krpm is not None
        assert result.electrical.revised_bldc_torque_constant_nm_per_conduction_a is not None
        assert result.electrical.revised_bldc_torque_constant_nm_per_phase_rms_a is not None
        assert result.electrical.bldc_waveform_semantics_status == "ideal_bldc_three_phase_y_120_degree_defined"
        assert result.electrical.bldc_power_balance_status == "validated_from_piecewise_and_numeric_integration"
        assert result.electrical.revised_back_emf_constant_phase_peak_v_per_rad_s is None
        assert result.electrical.revised_torque_constant_nm_per_phase_rms_a is None
        assert result.performance.required_voltage_semantics_status == "legacy_line_rms_requirement_model"
        assert math.isclose(
            result.performance.phase_current_rms_a,
            case["legacy_outputs"]["rated_current_rms_a"],
            rel_tol=REL_TOL,
            abs_tol=ABS_TOL,
        )
        assert math.isclose(
            result.performance.required_voltage_v,
            case["legacy_outputs"]["required_voltage_v"],
            rel_tol=REL_TOL,
            abs_tol=ABS_TOL,
        )
