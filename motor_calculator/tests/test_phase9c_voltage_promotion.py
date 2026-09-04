"""Phase 9C: corrected PMSM voltage promoted to the authoritative path.

After promotion the application must not carry two competing user-facing
engineering truths. The legacy value survives as a clearly named reference, but
it must no longer drive feasibility, the optimizer, the dashboard, the sweep or
normal exports.
"""

from __future__ import annotations

import csv
import math

import pytest

from helpers import build_sample_legacy_params
from motor_core import LegacyGuiMotorModelBridge, parse_legacy_gui_params
from motor_calculator.motor_core.voltage_semantics import (
    VOLTAGE_AUTHORITY_CORRECTED,
    VOLTAGE_AUTHORITY_LEGACY_REFERENCE,
    VOLTAGE_GUIDANCE_ZH,
    VOLTAGE_SEMANTICS_VERSION,
)
from motor_calculator.plots import build_dashboard_data
from motor_calculator.validation.design_feasibility import (
    FeasibilityCalculability,
    FeasibilitySeverity,
    evaluate_design_feasibility,
    same_basis_available_line_rms_v,
)


V2_VALUES = {
    "V_dc": 72.0,
    "P_rated": 600.0,
    "n_rated": 1800.0,
    "N_ph_turns": 42,
    "d_wire": 1.2,
    "n_parallel": 3,
    "slot_type": "半闭口槽",
    "coreless": False,
}

# A PMSM design the legacy basis calls feasible and the corrected basis does not.
VOLTAGE_LIMITED_VALUES = {
    "V_dc": 72.0,
    "P_rated": 600.0,
    "n_rated": 2200.0,
    "d_wire": 1.2,
    "slot_type": "半闭口槽",
    "coreless": False,
}


def _application_defaults():
    from motor_calculator.input_ux.metadata import APPLICATION_DEFAULTS

    return dict(APPLICATION_DEFAULTS)


def _evaluate(values):
    raw = _application_defaults()
    raw.update(values)
    parsed = parse_legacy_gui_params(raw)
    result = LegacyGuiMotorModelBridge(parsed).run_full_analysis()
    return parsed, result, evaluate_design_feasibility(parsed, result)


# ---------------------------------------------------------------------------
# STEP 3/4 authoritative definition and field semantics
# ---------------------------------------------------------------------------


def test_corrected_formula_is_frozen_as_specified():
    """The Phase 9C approved formulation, term by term."""

    parsed, result, _assessment = _evaluate(V2_VALUES)
    electrical, performance = result.electrical, result.performance
    omega_e = 2.0 * math.pi * performance.electrical_frequency_hz

    expected = (
        math.sqrt(3.0)
        * math.hypot(
            electrical.back_emf_phase_rms_v
            + performance.phase_current_rms_a * electrical.phase_resistance_ohm,
            performance.phase_current_rms_a * omega_e * electrical.line_inductance_h,
        )
        * 1.05
    )
    assert float(performance.required_voltage_line_rms_v) == pytest.approx(
        expected, rel=1e-15
    )


def test_authoritative_and_legacy_fields_are_both_named_explicitly():
    _parsed, result, assessment = _evaluate(V2_VALUES)
    performance = result.performance

    # Authoritative
    assert performance.required_voltage_line_rms_v is not None
    assert assessment.voltage_margin_line_rms_percent is not None
    assert assessment.available_voltage_line_rms_v is not None
    # Legacy, explicitly named
    assert performance.legacy_required_voltage_v == performance.required_voltage_v
    assert assessment.legacy_voltage_margin_percent is not None
    # They must differ, so the promotion is real
    assert performance.required_voltage_line_rms_v != performance.legacy_required_voltage_v
    assert (
        assessment.voltage_margin_line_rms_percent
        != assessment.legacy_voltage_margin_percent
    )


def test_provenance_is_exposed_without_fake_confidence():
    _parsed, result, assessment = _evaluate(V2_VALUES)

    assert result.performance.voltage_authority == VOLTAGE_AUTHORITY_CORRECTED
    assert assessment.voltage_model_provenance == VOLTAGE_AUTHORITY_CORRECTED
    assert VOLTAGE_SEMANTICS_VERSION.startswith("phase9c")
    # No invented confidence percentage anywhere in the provenance strings.
    assert "%" not in assessment.voltage_model_provenance


def test_user_guidance_states_the_basis_and_the_limit():
    assert "统一 line-RMS 基准" in VOLTAGE_GUIDANCE_ZH
    assert "dq 稳态模型" in VOLTAGE_GUIDANCE_ZH
    assert "稳态近似" in VOLTAGE_GUIDANCE_ZH
    assert "开关级" in VOLTAGE_GUIDANCE_ZH


# ---------------------------------------------------------------------------
# STEP 5 nomenclature aliases, non-breaking
# ---------------------------------------------------------------------------


def test_nomenclature_aliases_do_not_remove_old_names():
    _parsed, result, _assessment = _evaluate(V2_VALUES)
    electrical = result.electrical

    assert electrical.phase_synchronous_inductance_h == electrical.line_inductance_h
    assert electrical.terminal_resistance_ohm == electrical.line_resistance_ohm
    # Old names still present.
    assert electrical.line_inductance_h > 0.0
    assert electrical.line_resistance_ohm > 0.0
    assert electrical.phase_resistance_ohm > 0.0


# ---------------------------------------------------------------------------
# STEP 7 feasibility promotion
# ---------------------------------------------------------------------------


def test_feasibility_voltage_check_uses_the_corrected_value():
    parsed, result, assessment = _evaluate(V2_VALUES)

    assert assessment.required_voltage_line_rms_v == pytest.approx(
        float(result.performance.required_voltage_line_rms_v), rel=1e-15
    )
    assert assessment.voltage_margin_percent == pytest.approx(
        same_basis_available_line_rms_v(parsed["V_dc"])
        and (
            (
                same_basis_available_line_rms_v(parsed["V_dc"])
                - float(result.performance.required_voltage_line_rms_v)
            )
            / same_basis_available_line_rms_v(parsed["V_dc"])
            * 100.0
        ),
        rel=1e-12,
    )


def test_feasibility_severity_is_driven_by_the_corrected_margin():
    """The legacy basis calls this design feasible; the corrected basis must not,
    and the severity code must follow the corrected basis."""

    _parsed, _result, assessment = _evaluate(VOLTAGE_LIMITED_VALUES)

    assert assessment.legacy_voltage_margin_percent > 0.0
    assert assessment.voltage_margin_percent < 0.0
    assert any(issue.code == "VOLTAGE_MARGIN_SEVERE" for issue in assessment.issues)
    assert assessment.has_severe_design_risk


def test_legacy_margin_never_produces_a_voltage_severity_code():
    """Scan a grid: no VOLTAGE_* severity may be explained by the legacy value."""

    for speed in (1400.0, 1800.0, 2200.0, 2600.0):
        values = dict(VOLTAGE_LIMITED_VALUES)
        values["n_rated"] = speed
        _parsed, _result, assessment = _evaluate(values)
        severe = any(issue.code == "VOLTAGE_MARGIN_SEVERE" for issue in assessment.issues)
        assert severe == (assessment.voltage_margin_percent < 0.0)


def test_phase9b_alias_fields_still_resolve():
    _parsed, _result, assessment = _evaluate(V2_VALUES)

    assert assessment.corrected_required_voltage_line_rms_v == (
        assessment.required_voltage_line_rms_v
    )
    assert assessment.corrected_voltage_margin_percent == assessment.voltage_margin_percent


# ---------------------------------------------------------------------------
# STEP 8 BLDC safety
# ---------------------------------------------------------------------------


def test_bldc_same_basis_margin_remains_unsupported():
    raw = build_sample_legacy_params(waveform="梯形波")
    parsed = parse_legacy_gui_params(raw)
    result = LegacyGuiMotorModelBridge(parsed).run_full_analysis()
    assessment = evaluate_design_feasibility(parsed, result)

    assert result.performance.required_voltage_line_rms_v is None
    assert result.performance.voltage_authority == VOLTAGE_AUTHORITY_LEGACY_REFERENCE
    assert assessment.voltage_status is FeasibilityCalculability.NOT_ENOUGH_SEMANTICS
    assert assessment.voltage_margin_percent is None
    assert assessment.voltage_margin_line_rms_percent is None
    assert any(issue.code == "VOLTAGE_BASIS_UNAVAILABLE" for issue in assessment.issues)
    # The legacy value is still there for reference, and still clearly legacy.
    assert result.performance.legacy_required_voltage_v > 0.0


# ---------------------------------------------------------------------------
# STEP 12 dashboard promotion
# ---------------------------------------------------------------------------


def test_dashboard_primary_voltage_cards_show_corrected_values():
    parsed, result, assessment = _evaluate(V2_VALUES)
    data = build_dashboard_data(parsed, result, assessment)

    required = data.metric_by_key["required_voltage_v"]
    margin = data.metric_by_key["voltage_margin_percent"]

    assert required.label_zh == "所需线电压 RMS"
    assert required.value == pytest.approx(
        float(result.performance.required_voltage_line_rms_v), rel=1e-15
    )
    assert margin.label_zh == "同基电压裕量"
    assert margin.value == pytest.approx(assessment.voltage_margin_percent, rel=1e-15)


def test_dashboard_legacy_values_live_under_a_legacy_grouping():
    parsed, result, assessment = _evaluate(V2_VALUES)
    data = build_dashboard_data(parsed, result, assessment)

    legacy_keys = {metric.key for metric in data.legacy_diagnostic_metrics}
    assert "legacy_required_voltage_v" in legacy_keys
    assert "legacy_voltage_margin_percent" in legacy_keys
    for metric in data.legacy_diagnostic_metrics:
        assert "兼容" in metric.label_zh or "legacy" in metric.label_zh.lower()

    primary_keys = {metric.key for metric in data.electromagnetic_metrics}
    assert "legacy_required_voltage_v" not in primary_keys


# ---------------------------------------------------------------------------
# STEP 13 sweep promotion
# ---------------------------------------------------------------------------


def test_speed_sweep_points_use_the_corrected_voltage():
    from motor_calculator.plots import run_speed_sweep

    raw = _application_defaults()
    raw.update(V2_VALUES)
    sweep = run_speed_sweep(raw, 1400.0, 2600.0, point_count=5)

    for point in sweep.points:
        values = dict(raw)
        values["n_rated"] = point.speed_rpm
        _parsed, result, assessment = _evaluate(values)
        assert point.required_voltage_line_rms_v == pytest.approx(
            float(result.performance.required_voltage_line_rms_v), rel=1e-12
        )
        assert point.voltage_margin_percent == pytest.approx(
            assessment.voltage_margin_percent, rel=1e-12
        )
        assert point.legacy_required_voltage_line_rms_v == pytest.approx(
            float(result.performance.required_voltage_v), rel=1e-12
        )


def test_speed_sweep_legacy_curve_is_not_default_visible():
    from motor_calculator.plots import build_speed_sweep_series, run_speed_sweep

    raw = _application_defaults()
    raw.update(V2_VALUES)
    series = build_speed_sweep_series(run_speed_sweep(raw, 1400.0, 2600.0, point_count=3))
    by_key = {item.key: item for item in series}

    assert "required_voltage" in by_key
    assert "available_voltage" in by_key
    assert "voltage_margin" in by_key
    assert by_key["legacy_required_voltage"].default_visible is False
    assert by_key["required_voltage"].default_visible is True


def test_speed_sweep_keeps_the_scope_warning():
    from motor_calculator.plots import run_speed_sweep
    from motor_calculator.plots.performance import SPEED_SWEEP_SCOPE_STATEMENT_ZH

    raw = _application_defaults()
    raw.update(V2_VALUES)
    sweep = run_speed_sweep(raw, 1400.0, 2600.0, point_count=3)

    assert SPEED_SWEEP_SCOPE_STATEMENT_ZH in sweep.source_label_zh
    assert "不是完整转矩-转速能力包络" in SPEED_SWEEP_SCOPE_STATEMENT_ZH


def test_speed_sweep_csv_exports_both_but_names_them_correctly(tmp_path):
    from motor_calculator.plots import export_speed_sweep_csv, run_speed_sweep

    raw = _application_defaults()
    raw.update(V2_VALUES)
    sweep = run_speed_sweep(raw, 1400.0, 2600.0, point_count=3)
    destination = export_speed_sweep_csv(sweep, tmp_path / "sweep.csv")

    with destination.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert rows
    assert "voltage_required_line_rms_v" in rows[0]
    assert "voltage_margin_line_rms_percent" in rows[0]
    assert "legacy_required_voltage_v" in rows[0]
    for row, point in zip(rows, sweep.points):
        assert float(row["voltage_required_line_rms_v"]) == pytest.approx(
            point.required_voltage_line_rms_v, rel=1e-12
        )
        assert float(row["legacy_required_voltage_v"]) == pytest.approx(
            point.legacy_required_voltage_line_rms_v, rel=1e-12
        )


# ---------------------------------------------------------------------------
# STEP 15 export promotion
# ---------------------------------------------------------------------------


def _export_payload(values):
    import importlib

    mixin = importlib.import_module("gui.main_window").MotorCalculatorAppMixin
    raw = _application_defaults()
    raw.update(values)
    _parsed, result, _assessment = _evaluate(values)

    class _Stub(mixin):
        def _collect_raw_params(self):
            return dict(raw)

    return mixin.rc2_export_payload(object.__new__(_Stub), result), result


def test_export_uses_authoritative_field_names_for_corrected_values():
    payload, result = _export_payload(V2_VALUES)

    assert payload["required_voltage_line_rms_v"] == pytest.approx(
        float(result.performance.required_voltage_line_rms_v), rel=1e-15
    )
    assert payload["available_voltage_line_rms_v"] is not None
    assert payload["voltage_margin_line_rms_percent"] is not None
    assert payload["voltage_model_provenance"] == VOLTAGE_AUTHORITY_CORRECTED
    assert payload["voltage_semantics_version"] == VOLTAGE_SEMANTICS_VERSION


def test_export_never_publishes_a_legacy_value_under_an_authoritative_name():
    payload, result = _export_payload(V2_VALUES)
    legacy_value = float(result.performance.required_voltage_v)

    assert payload["legacy_required_voltage_v"] == pytest.approx(legacy_value, rel=1e-15)
    assert payload["required_voltage_line_rms_v"] != pytest.approx(legacy_value, rel=1e-9)
    assert payload["legacy_voltage_margin_percent"] != pytest.approx(
        payload["voltage_margin_line_rms_percent"], rel=1e-9
    )


# ---------------------------------------------------------------------------
# STEP 20 bad-design regression
# ---------------------------------------------------------------------------


def test_voltage_limited_design_is_rejected_end_to_end():
    parsed, result, assessment = _evaluate(VOLTAGE_LIMITED_VALUES)
    data = build_dashboard_data(parsed, result, assessment)

    assert assessment.voltage_margin_percent < 0.0
    assert assessment.has_severe_design_risk
    assert data.metric_by_key["voltage_margin_percent"].value < 0.0
    # The legacy value would have said this is fine.
    assert assessment.legacy_voltage_margin_percent > 0.0


# ---------------------------------------------------------------------------
# STEP 21 feasible v2 regression
# ---------------------------------------------------------------------------


def test_v2_is_the_primary_accepted_regression_case():
    _parsed, result, assessment = _evaluate(V2_VALUES)

    assert not assessment.has_error
    assert not assessment.has_severe_design_risk
    assert not any(
        issue.severity is FeasibilitySeverity.WARNING for issue in assessment.issues
    )
    assert assessment.voltage_margin_percent >= 15.0
    assert assessment.current_density_a_per_mm2 <= 5.0
    assert 0.25 <= assessment.slot_fill_factor <= 0.50
    assert result.performance.rated_torque_nm > 0.0


# ---------------------------------------------------------------------------
# STEP 22 legacy boundary
# ---------------------------------------------------------------------------


def test_legacy_output_still_exists_but_controls_nothing():
    _parsed, result, assessment = _evaluate(VOLTAGE_LIMITED_VALUES)

    # It exists.
    assert result.performance.required_voltage_v > 0.0
    assert result.performance.legacy_required_voltage_v > 0.0
    assert assessment.legacy_required_voltage_line_rms_v > 0.0
    assert assessment.legacy_voltage_margin_percent is not None
    # It controls nothing: the design is rejected despite a positive legacy margin.
    assert assessment.legacy_voltage_margin_percent > 0.0
    assert assessment.has_severe_design_risk


def test_legacy_baseline_anchored_field_is_bit_identical():
    """`required_voltage_v` is anchored in the frozen baseline and must not move."""

    import json
    from pathlib import Path

    fixture = (
        Path(__file__).resolve().parent / "fixtures" / "legacy_baseline.json"
    )
    cases = json.loads(fixture.read_text(encoding="utf-8"))["cases"]
    for case in cases:
        result = LegacyGuiMotorModelBridge(case["legacy_inputs"]).run_full_analysis()
        assert float(result.performance.required_voltage_v) == pytest.approx(
            case["legacy_outputs"]["required_voltage_v"], rel=1e-12
        )
