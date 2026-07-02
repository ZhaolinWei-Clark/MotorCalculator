"""Pytest-style regression tests against the preserved legacy baseline."""

from __future__ import annotations

import json
import math
from pathlib import Path

from motor_core import calculate_from_legacy_params

REL_TOL = 1e-8
ABS_TOL = 1e-10

EXPECTED_OUTPUT_FIELDS = [
    "phi_pole_wb",
    "bg_peak_t",
    "bg_avg_t",
    "bg_rms_t",
    "back_emf_phase_rms_v",
    "back_emf_line_rms_v",
    "ke_v_per_krpm",
    "kt_nm_per_a_rms",
    "phase_resistance_ohm",
    "phase_inductance_h",
    "rated_current_rms_a",
    "copper_loss_w",
    "core_loss_w",
    "mechanical_loss_w",
    "input_power_w",
    "output_power_w",
    "efficiency_percent",
    "required_voltage_v",
]


def _load_fixture():
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "legacy_baseline.json"
    with fixture_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _extract_outputs(result):
    return {
        "phi_pole_wb": result.magnetic.Phi_pole,
        "bg_peak_t": result.magnetic.Bg_peak,
        "bg_avg_t": result.magnetic.Bg_avg,
        "bg_rms_t": result.magnetic.Bg_rms,
        "back_emf_phase_rms_v": result.electrical.E_phase_rms,
        "back_emf_line_rms_v": result.electrical.E_line_rms,
        "ke_v_per_krpm": result.electrical.Ke,
        "kt_nm_per_a_rms": result.electrical.Kt,
        "phase_resistance_ohm": result.electrical.R_phase,
        "phase_inductance_h": result.electrical.L_phase,
        "rated_current_rms_a": result.performance.I_phase_rms,
        "copper_loss_w": result.performance.P_cu,
        "core_loss_w": result.performance.P_core,
        "mechanical_loss_w": result.performance.P_mech,
        "input_power_w": result.performance.P_in,
        "output_power_w": result.performance.P_out,
        "efficiency_percent": result.performance.Efficiency,
        "required_voltage_v": result.performance.V_required,
    }


def _build_diff_report(case_name, expected_outputs, actual_outputs):
    mismatches = []
    for field_name in EXPECTED_OUTPUT_FIELDS:
        expected_value = expected_outputs[field_name]
        actual_value = actual_outputs[field_name]
        if math.isclose(expected_value, actual_value, rel_tol=REL_TOL, abs_tol=ABS_TOL):
            continue
        absolute_error = abs(actual_value - expected_value)
        relative_error = absolute_error / abs(expected_value) if expected_value != 0 else float("inf")
        mismatches.append(
            "\n".join(
                [
                    f"字段: {field_name}",
                    f"原始结果: {expected_value!r}",
                    f"新结果: {actual_value!r}",
                    f"绝对误差: {absolute_error!r}",
                    f"相对误差: {relative_error!r}",
                    "不一致原因: 需要人工确认；当前阶段不应擅自修改基准数据。",
                ]
            )
        )
    if mismatches:
        raise AssertionError(f"Case {case_name} regression mismatch:\n\n" + "\n\n".join(mismatches))


def test_legacy_baseline_regression():
    fixture = _load_fixture()
    for case in fixture["cases"]:
        result = calculate_from_legacy_params(case["legacy_inputs"])
        actual_outputs = _extract_outputs(result)
        _build_diff_report(case["name"], case["legacy_outputs"], actual_outputs)
