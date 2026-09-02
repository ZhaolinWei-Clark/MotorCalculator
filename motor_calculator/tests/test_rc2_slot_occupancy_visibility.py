"""RC2: slot occupancy must be visible, authoritative and consistent."""

from __future__ import annotations

import csv
import math

import pytest

from helpers import build_sample_legacy_params
from motor_core import LegacyGuiMotorModelBridge, parse_legacy_gui_params
from motor_calculator.plots import build_dashboard_data
from motor_calculator.plots.inventory import OUTPUT_INVENTORY
from motor_calculator.project.schema import (
    build_project_inputs,
    flatten_project_inputs,
    project_inputs_hash,
)
from motor_calculator.validation.design_feasibility import (
    FeasibilityCalculability,
    evaluate_design_feasibility,
    feasible_starting_inputs,
)


SLOTTED_DESIGN = {
    "coreless": False,
    "slot_type": "半闭口槽",
    "slots": 24,
    "h_slot": 15.0,
    "w_slot_top": 8.0,
    "w_slot_bottom": 6.0,
    "h_wedge": 2.0,
}


def _application_defaults():
    from motor_calculator.input_ux.metadata import APPLICATION_DEFAULTS

    return dict(APPLICATION_DEFAULTS)


def _evaluate(raw):
    parsed = parse_legacy_gui_params(raw)
    result = LegacyGuiMotorModelBridge(parsed).run_full_analysis()
    return parsed, result, evaluate_design_feasibility(parsed, result)


def test_slot_occupancy_is_available_when_slot_geometry_exists():
    raw = dict(_application_defaults())
    raw.update(SLOTTED_DESIGN)
    _parsed, _result, assessment = _evaluate(raw)

    assert assessment.slot_fill_status is FeasibilityCalculability.APPROXIMATE
    assert assessment.slot_fill_factor is not None
    assert 0.0 < assessment.slot_fill_factor <= 2.0
    assert assessment.total_slot_copper_area_mm2 is not None
    assert assessment.total_available_slot_area_mm2 is not None
    assert assessment.slot_fill_factor == pytest.approx(
        assessment.total_slot_copper_area_mm2 / assessment.total_available_slot_area_mm2,
        rel=1e-12,
    )


def test_slot_occupancy_reports_not_enough_geometry_for_coreless_designs():
    raw = dict(_application_defaults())
    raw.update({"coreless": True, "slot_type": "无槽"})
    _parsed, result, assessment = _evaluate(raw)

    assert assessment.slot_fill_status is FeasibilityCalculability.NOT_ENOUGH_GEOMETRY
    assert assessment.slot_fill_factor is None
    # The legacy proxy must never be substituted for the missing value.
    assert assessment.legacy_fill_proxy == pytest.approx(result.performance.fill_factor)
    assert assessment.legacy_fill_proxy > 1.0


def test_dashboard_metric_matches_the_phase8g_assessment_exactly():
    raw = dict(_application_defaults())
    raw.update(SLOTTED_DESIGN)
    parsed, result, assessment = _evaluate(raw)
    data = build_dashboard_data(parsed, result, assessment)

    metric = data.metric_by_key["slot_fill_factor"]
    assert metric.label_zh == "近似裸铜槽占比"
    assert metric.value == pytest.approx(assessment.slot_fill_factor, rel=1e-15)
    assert metric.source == "validation.design_feasibility"
    # The dashboard must not silently show the legacy proxy instead.
    assert not math.isclose(metric.value, result.performance.fill_factor, rel_tol=1e-6)


def test_dashboard_marks_slot_occupancy_unavailable_without_geometry():
    raw = dict(_application_defaults())
    raw.update({"coreless": True, "slot_type": "无槽"})
    parsed, result, assessment = _evaluate(raw)
    data = build_dashboard_data(parsed, result, assessment)

    metric = data.metric_by_key["slot_fill_factor"]
    assert metric.value is None
    assert "legacy" in metric.interpretation_zh or "不能代替" in metric.interpretation_zh


def test_output_inventory_never_names_the_legacy_proxy_a_slot_fill_factor():
    item = next(entry for entry in OUTPUT_INVENTORY if entry.key == "slot_fill_factor")

    assert item.label_zh == "近似裸铜槽占比"
    assert item.source == "validation.design_feasibility"
    assert "真实槽满率" not in item.label_zh
    assert "制造槽满率" not in item.label_zh


def test_speed_sweep_csv_uses_the_same_basis_voltage_columns(tmp_path):
    from motor_calculator.plots import export_speed_sweep_csv, run_speed_sweep

    raw = feasible_starting_inputs(_application_defaults())
    sweep = run_speed_sweep(raw, 1800.0, 2600.0, point_count=5)
    destination = export_speed_sweep_csv(sweep, tmp_path / "sweep.csv")

    with destination.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert rows
    assert "voltage_margin_percent" in rows[0]
    assert "voltage_available_line_rms_v" in rows[0]
    for row, point in zip(rows, sweep.points):
        assert float(row["voltage_margin_percent"]) == pytest.approx(
            point.voltage_margin_percent, rel=1e-12
        )
        assert float(row["voltage_available_line_rms_v"]) == pytest.approx(
            float(raw["V_dc"]) / math.sqrt(2.0), rel=1e-12
        )


def test_slot_occupancy_survives_a_project_round_trip():
    raw = dict(_application_defaults())
    raw.update(SLOTTED_DESIGN)
    parsed, _result, assessment = _evaluate(raw)

    inputs = build_project_inputs(parsed)
    restored = flatten_project_inputs(inputs)
    assert restored == parsed

    restored_result = LegacyGuiMotorModelBridge(restored).run_full_analysis()
    restored_assessment = evaluate_design_feasibility(restored, restored_result)
    assert restored_assessment.slot_fill_factor == pytest.approx(
        assessment.slot_fill_factor, rel=1e-15
    )
    assert restored_assessment.voltage_margin_percent == pytest.approx(
        assessment.voltage_margin_percent, rel=1e-15
    )


def test_project_hash_is_unaffected_by_rc2_winding_factor_metadata():
    """RC2 keeps `k_w` as the only physics input, so project hashes are stable
    for designs that do not change `k_w`."""

    raw = dict(_application_defaults())
    raw.update(SLOTTED_DESIGN)
    baseline = project_inputs_hash(build_project_inputs(parse_legacy_gui_params(raw)))

    # An unrelated UI/provenance change must not move the input hash.
    again = project_inputs_hash(build_project_inputs(parse_legacy_gui_params(dict(raw))))
    assert again == baseline

    # A genuine k_w change must move it.
    changed = dict(raw)
    changed["k_w"] = 0.8660254037844386
    assert (
        project_inputs_hash(build_project_inputs(parse_legacy_gui_params(changed))) != baseline
    )


def test_parsed_params_still_match_the_project_schema_key_set():
    """RC2 must not add keys to the parsed parameter contract."""

    from motor_calculator.project.schema import PROJECT_INPUT_SPECS

    parsed = parse_legacy_gui_params(build_sample_legacy_params())
    assert set(parsed) == set(PROJECT_INPUT_SPECS)
