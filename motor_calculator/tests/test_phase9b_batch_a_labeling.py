"""Phase 9B Batch A: labelling only, with a hard zero-numerical-change guard.

Batch A carries no formula change. These tests pin both halves of that promise:
the limitation wording must be present and specific, and every loss number must
stay bit-identical to the pre-Batch-A values.
"""

from __future__ import annotations

import pytest

from motor_core import LegacyGuiMotorModelBridge, parse_legacy_gui_params
from motor_calculator.plots import build_dashboard_data
from motor_calculator.plots.inventory import OUTPUT_INVENTORY
from motor_calculator.validation.design_feasibility import (
    evaluate_design_feasibility,
    feasible_starting_inputs,
)


# Values recorded on codex/rc2-engineering-corrections @ e7e9556 (707 passed),
# immediately before Batch A. Batch A must not move any of them.
PRE_BATCH_A_LOSSES = {
    "application_default": {
        "copper_loss_w": 39.53646488447724,
        "eddy_loss_w": 18.93992541043538,
        "core_loss_w": 8.0,
        "mechanical_loss_w": 3.5122759932001975,
        "input_power_w": 869.9886662881128,
        "efficiency_percent": 91.95522091262109,
    },
    "manufacturability_start": {
        "copper_loss_w": 16.789919517415793,
        "eddy_loss_w": 44.59924272582511,
        "core_loss_w": 6.0,
        "mechanical_loss_w": 2.3219444123047914,
        "input_power_w": 669.7111066555457,
        "efficiency_percent": 89.59086896383214,
    },
}


def _application_defaults():
    from motor_calculator.input_ux.metadata import APPLICATION_DEFAULTS

    return dict(APPLICATION_DEFAULTS)


def _cases():
    return {
        "application_default": _application_defaults(),
        "manufacturability_start": feasible_starting_inputs(_application_defaults()),
    }


def _inventory(key):
    return next(item for item in OUTPUT_INVENTORY if item.key == key)


def _dashboard_loss_metric(raw, key):
    parsed = parse_legacy_gui_params(raw)
    result = LegacyGuiMotorModelBridge(parsed).run_full_analysis()
    assessment = evaluate_design_feasibility(parsed, result)
    data = build_dashboard_data(parsed, result, assessment)
    return next(metric for metric in data.loss_metrics if metric.key == key)


# ---------------------------------------------------------------------------
# Zero numerical change
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_name", sorted(PRE_BATCH_A_LOSSES))
def test_batch_a_changes_no_loss_number(case_name):
    raw = _cases()[case_name]
    performance = LegacyGuiMotorModelBridge(
        parse_legacy_gui_params(raw)
    ).run_full_analysis().performance

    for field, expected in PRE_BATCH_A_LOSSES[case_name].items():
        actual = float(getattr(performance, field))
        assert actual == expected, (
            f"{case_name}.{field} moved during a labelling-only batch: "
            f"{actual!r} != {expected!r}"
        )


# ---------------------------------------------------------------------------
# A1 conductor eddy loss must be marked experimental / approximate
# ---------------------------------------------------------------------------


def test_a1_eddy_loss_inventory_is_marked_experimental():
    item = _inventory("eddy_loss_w")

    assert "EXPERIMENTAL" in item.confidence.upper()
    assert "实验性" in item.label_zh or "EXPERIMENTAL" in item.label_zh.upper()
    # The derivation must say the field basis is a single scalar, not local.
    assert "scalar" in item.derivation.lower()
    assert "air-gap" in item.derivation.lower() or "air gap" in item.derivation.lower()


def test_a1_eddy_loss_dashboard_names_every_unresolved_effect():
    metric = _dashboard_loss_metric(_application_defaults(), "eddy_loss_w")
    text = metric.interpretation_zh

    assert "实验性" in text or "近似" in text
    for required in ("气隙", "端部", "电枢反应", "邻近效应", "线股"):
        assert required in text, f"missing limitation term {required!r} in {text!r}"
    assert metric.value == pytest.approx(
        PRE_BATCH_A_LOSSES["application_default"]["eddy_loss_w"], abs=0.0
    )


# ---------------------------------------------------------------------------
# A2 core loss must not read as a validated stator-core-loss prediction
# ---------------------------------------------------------------------------


def test_a2_core_loss_inventory_is_not_presented_as_a_validated_core_loss_model():
    item = _inventory("core_loss_w")

    assert "铁芯损耗" != item.label_zh, "the bare label implies a stator core-loss model"
    assert "集总" in item.label_zh or "经验" in item.label_zh
    assert "EMPIRICAL" in item.confidence.upper() or "LUMPED" in item.confidence.upper()


def test_a2_core_loss_dashboard_states_the_decoupling_and_the_rotor_iron():
    metric = _dashboard_loss_metric(_application_defaults(), "core_loss_w")
    text = metric.interpretation_zh

    # It is a rated-point lumped constant, decoupled from speed and flux density.
    assert "转速" in text and "磁密" in text
    # Coreless does not mean "no ferromagnetic material": rotor back iron remains.
    assert "转子" in text and ("背铁" in text or "铁" in text)
    assert "无铁芯" in text or "coreless" in text.lower()
    assert metric.value == pytest.approx(
        PRE_BATCH_A_LOSSES["application_default"]["core_loss_w"], abs=0.0
    )


def test_a2_core_loss_is_still_reported_for_coreless_designs():
    """Batch A must not zero the term; that would be an unapproved model change."""

    raw = _application_defaults()
    raw.update({"coreless": True, "slot_type": "无槽"})
    performance = LegacyGuiMotorModelBridge(
        parse_legacy_gui_params(raw)
    ).run_full_analysis().performance

    assert performance.core_loss_w > 0.0


# ---------------------------------------------------------------------------
# A3 speed sweep labelling
# ---------------------------------------------------------------------------


REQUIRED_SWEEP_SENTENCE = "基于当前模型逐点重算，不是完整转矩-转速能力包络。"


def test_a3_speed_sweep_result_carries_the_required_sentence():
    from motor_calculator.plots import run_speed_sweep

    result = run_speed_sweep(
        feasible_starting_inputs(_application_defaults()), 1800.0, 2600.0, point_count=3
    )
    assert REQUIRED_SWEEP_SENTENCE in result.source_label_zh


def test_a3_every_speed_sweep_series_carries_the_required_sentence():
    from motor_calculator.plots import build_speed_sweep_series, run_speed_sweep

    result = run_speed_sweep(
        feasible_starting_inputs(_application_defaults()), 1800.0, 2600.0, point_count=3
    )
    for series in build_speed_sweep_series(result):
        assert REQUIRED_SWEEP_SENTENCE in series.source_label_zh


def test_a3_rendered_figure_title_carries_the_required_sentence():
    pytest.importorskip("matplotlib")
    from motor_calculator.plots import render_speed_sweep_figure, run_speed_sweep

    result = run_speed_sweep(
        feasible_starting_inputs(_application_defaults()), 1800.0, 2600.0, point_count=3
    )
    figure = render_speed_sweep_figure(result)
    try:
        assert REQUIRED_SWEEP_SENTENCE in figure._suptitle.get_text()
    finally:
        figure.clf()


# ---------------------------------------------------------------------------
# The limitation must reach the report and the machine-readable export
# ---------------------------------------------------------------------------


def _export_stub(raw):
    import importlib

    mixin = importlib.import_module("gui.main_window").MotorCalculatorAppMixin

    class _Stub(mixin):
        def _collect_raw_params(self):
            return dict(raw)

    return mixin, object.__new__(_Stub)


def test_export_payload_carries_loss_model_status():
    raw = _application_defaults()
    result = LegacyGuiMotorModelBridge(parse_legacy_gui_params(raw)).run_full_analysis()
    mixin, stub = _export_stub(raw)
    payload = mixin.rc2_export_payload(stub, result)

    assert payload["eddy_loss_model_status"] == "EXPERIMENTAL_SCALAR_AIRGAP_FIELD"
    assert payload["core_loss_model_status"] == "EMPIRICAL_LUMPED_RATED_POINT"
    assert "eddy_loss_limitation_zh" in payload
    assert "core_loss_limitation_zh" in payload
    # Values themselves are untouched.
    assert payload["eddy_loss_w"] == pytest.approx(
        PRE_BATCH_A_LOSSES["application_default"]["eddy_loss_w"], abs=0.0
    )
    assert payload["core_loss_w"] == pytest.approx(
        PRE_BATCH_A_LOSSES["application_default"]["core_loss_w"], abs=0.0
    )


def test_detailed_report_summary_states_both_loss_limitations():
    from motor_calculator.motor_core.loss_semantics import (
        CORE_LOSS_LIMITATION_ZH,
        EDDY_LOSS_LIMITATION_ZH,
        loss_limitation_report_lines_zh,
    )

    lines = "\n".join(loss_limitation_report_lines_zh())
    assert EDDY_LOSS_LIMITATION_ZH in lines
    assert CORE_LOSS_LIMITATION_ZH in lines
    assert "涡流" in lines and "磁性损耗" in lines
