"""Phase 8G engineering-feasibility semantics and baseline tests."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from motor_calculator.input_ux import APPLICATION_DEFAULTS
from motor_calculator.motor_core import LegacyGuiMotorModelBridge, parse_legacy_gui_params
from motor_calculator.presets import apply_preset, default_preset_registry
from motor_calculator.project import create_project_document, flatten_project_inputs, load_project, save_project
from motor_calculator.validation.design_feasibility import (
    FEASIBLE_STARTING_OVERRIDES,
    FeasibilityCalculability,
    FeasibilitySeverity,
    evaluate_design_feasibility,
    feasible_starting_inputs,
    format_feasibility_messages_zh,
)


ROOT = Path(__file__).resolve().parents[2]


def _run(parameters):
    result = LegacyGuiMotorModelBridge(parse_legacy_gui_params(parameters)).run_full_analysis()
    return result, evaluate_design_feasibility(parameters, result)


def _feasible_inputs():
    preset = default_preset_registry().get("design.manufacturability_start.v1")
    return apply_preset(APPLICATION_DEFAULTS, preset)


def test_current_density_uses_phase_rms_and_one_conductor_per_equal_branch() -> None:
    parameters = _feasible_inputs()
    result, assessment = _run(parameters)
    area = math.pi * (parameters["d_wire"] / 2.0) ** 2
    expected = result.performance.phase_current_rms_a / parameters["n_parallel"] / area
    assert assessment.current_density_a_per_mm2 == pytest.approx(expected)
    assert assessment.current_density_a_per_mm2 == pytest.approx(
        result.performance.current_density_a_per_mm2
    )
    assert assessment.current_density_status is FeasibilityCalculability.CALCULABLE


def test_current_density_does_not_substitute_sinusoidal_peak_current() -> None:
    parameters = _feasible_inputs()
    result, assessment = _run(parameters)
    assert result.performance.phase_current_peak_a == pytest.approx(
        math.sqrt(2.0) * result.performance.phase_current_rms_a
    )
    reconstructed_rms = (
        assessment.current_density_a_per_mm2
        * assessment.conductor_copper_area_mm2
        * parameters["n_parallel"]
    )
    assert reconstructed_rms == pytest.approx(result.performance.phase_current_rms_a)
    assert reconstructed_rms != pytest.approx(result.performance.phase_current_peak_a)


def test_parallel_paths_reduce_conductor_current_density_with_equal_sharing() -> None:
    one = dict(_feasible_inputs(), n_parallel=1)
    two = dict(_feasible_inputs(), n_parallel=2)
    _, one_assessment = _run(one)
    _, two_assessment = _run(two)
    assert two_assessment.phase_current_rms_a == pytest.approx(one_assessment.phase_current_rms_a)
    assert two_assessment.current_density_a_per_mm2 == pytest.approx(
        one_assessment.current_density_a_per_mm2 / 2.0
    )


def test_slot_fill_counts_global_phase_turns_conductor_sides_and_slots_once() -> None:
    parameters = _feasible_inputs()
    _, assessment = _run(parameters)
    conductor_area = math.pi * (parameters["d_wire"] / 2.0) ** 2
    expected_copper = (
        3 * 2 * parameters["N_ph_turns"] * parameters["n_parallel"] * conductor_area
    )
    per_slot_available = (
        (parameters["w_slot_top"] + parameters["w_slot_bottom"]) / 2.0
        * parameters["h_slot"]
        - parameters["w_slot_top"] * parameters["h_wedge"]
    )
    expected_available = parameters["slots"] * per_slot_available
    assert assessment.total_slot_copper_area_mm2 == pytest.approx(expected_copper)
    assert assessment.total_available_slot_area_mm2 == pytest.approx(expected_available)
    assert assessment.slot_fill_factor == pytest.approx(expected_copper / expected_available)
    assert assessment.slot_fill_status is FeasibilityCalculability.APPROXIMATE


def test_turns_per_phase_is_distributed_across_slots_not_repeated_per_slot() -> None:
    parameters = _feasible_inputs()
    _, assessment = _run(parameters)
    wrongly_repeated = assessment.slot_fill_factor * parameters["slots"]
    assert assessment.slot_fill_factor < 0.5
    assert wrongly_repeated > 1.0


def test_slotless_design_reports_insufficient_geometry_not_unmanufacturable() -> None:
    parameters = dict(APPLICATION_DEFAULTS)
    _, assessment = _run(parameters)
    assert assessment.slot_fill_factor is None
    assert assessment.slot_fill_status is FeasibilityCalculability.NOT_ENOUGH_GEOMETRY
    assert "SLOT_FILL_SEVERE" not in {issue.code for issue in assessment.issues}
    assert assessment.legacy_fill_proxy > 0.8


def test_voltage_comparison_uses_consistent_svpwm_line_rms_basis() -> None:
    parameters = _feasible_inputs()
    result, assessment = _run(parameters)
    phase_peak = parameters["V_dc"] / math.sqrt(3.0)
    line_rms = phase_peak * math.sqrt(3.0 / 2.0)
    assert assessment.available_voltage_line_rms_v == pytest.approx(line_rms)
    assert assessment.available_voltage_line_rms_v == pytest.approx(
        parameters["V_dc"] / math.sqrt(2.0)
    )
    assert assessment.required_voltage_line_rms_v == pytest.approx(
        result.performance.required_voltage_v
    )
    assert assessment.voltage_status is FeasibilityCalculability.APPROXIMATE


def test_bldc_voltage_basis_remains_unavailable_without_waveform_assumption() -> None:
    parameters = dict(_feasible_inputs(), waveform="梯形波")
    _, assessment = _run(parameters)
    assert assessment.available_voltage_line_rms_v is None
    assert assessment.voltage_margin_percent is None
    assert assessment.voltage_status is FeasibilityCalculability.NOT_ENOUGH_SEMANTICS
    assert "VOLTAGE_BASIS_UNAVAILABLE" in {issue.code for issue in assessment.issues}


def test_feasible_starting_example_has_no_error_warning_or_severe_risk() -> None:
    parameters = _feasible_inputs()
    result, assessment = _run(parameters)
    assert not assessment.has_error
    assert not assessment.has_severe_design_risk
    assert all(issue.severity is FeasibilitySeverity.INFO for issue in assessment.issues)
    assert assessment.current_density_a_per_mm2 <= 5.0
    assert assessment.slot_fill_factor == pytest.approx(0.31768914474503523)
    assert assessment.voltage_margin_percent == pytest.approx(15.62548387156598)
    assert result.performance.output_power_w == 600.0


def test_intentionally_bad_design_still_triggers_multiple_severe_risks() -> None:
    parameters = dict(
        _feasible_inputs(),
        V_dc=48.0,
        P_rated=10000.0,
        N_ph_turns=200,
        d_wire=1.2,
    )
    _, assessment = _run(parameters)
    severe_codes = {
        issue.code
        for issue in assessment.issues
        if issue.severity is FeasibilitySeverity.SEVERE_DESIGN_RISK
    }
    assert {"CURRENT_DENSITY_SEVERE", "SLOT_FILL_SEVERE", "VOLTAGE_MARGIN_SEVERE"} <= severe_codes


def test_messages_expose_values_and_actionable_guidance_outside_gui() -> None:
    parameters = dict(_feasible_inputs(), P_rated=1200.0, d_wire=0.8)
    _, assessment = _run(parameters)
    messages = "\n".join(format_feasibility_messages_zh(assessment))
    assert "A/mm²" in messages
    assert "可用/所需线电压 RMS" in messages
    assert "增大导体截面积" in messages
    source = (ROOT / "motor_calculator" / "validation" / "design_feasibility.py").read_text(encoding="utf-8")
    assert "tkinter" not in source


def test_project_round_trip_reproduces_identical_feasibility_state(tmp_path: Path) -> None:
    inputs = _feasible_inputs()
    document = create_project_document("Phase 8G feasible", inputs)
    path = save_project(document, tmp_path / "phase8g.motorproj")
    restored = flatten_project_inputs(load_project(path).inputs)
    _, before = _run(inputs)
    _, after = _run(restored)
    assert before.to_dict() == after.to_dict()


def test_preset_is_explicit_partial_override_and_defaults_remain_frozen() -> None:
    preset = default_preset_registry().get("design.manufacturability_start.v1")
    assert dict(preset.values) == FEASIBLE_STARTING_OVERRIDES
    assert apply_preset(APPLICATION_DEFAULTS, preset) == feasible_starting_inputs(APPLICATION_DEFAULTS)
    assert APPLICATION_DEFAULTS["V_dc"] == 48.0
    assert APPLICATION_DEFAULTS["P_rated"] == 800.0
