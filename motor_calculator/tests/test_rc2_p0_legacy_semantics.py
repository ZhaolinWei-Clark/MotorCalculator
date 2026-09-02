"""RC2 Step 3: deterministic reproduction of the two RC1 P0 findings.

These tests intentionally document the *current* legacy behaviour so that the
RC2 corrections have a regression anchor. They do not assert that the legacy
behaviour is desirable -- they assert that it is inconsistent with the Phase 8G
feasibility semantics, which is exactly the defect under repair.
"""

from __future__ import annotations

import importlib
import math

import pytest

from helpers import build_sample_legacy_params
from motor_core import LegacyGuiMotorModelBridge, parse_legacy_gui_params
from motor_calculator.validation.design_feasibility import (
    FeasibilityCalculability,
    FeasibilitySeverity,
    evaluate_design_feasibility,
    feasible_starting_inputs,
)


# The legacy claim is identified by its own wording. The modern layer also
# mentions the phrase "无法制造", but only inside the negation
# "不得用于宣称无法制造", so a bare substring match is not sufficient.
LEGACY_MANUFACTURABILITY_TEXT = "填充系数超过实际限制"


def _claims_unmanufacturable(text: str) -> bool:
    return LEGACY_MANUFACTURABILITY_TEXT in text or (
        "无法制造" in text and "不得用于宣称" not in text
    )


LEGACY_INCREASE_TURNS_TEXT = "考虑增加匝数"


def _legacy_base_app_class():
    """The unmodified legacy GUI class, i.e. the pre-Phase-8G behaviour."""

    main_window = importlib.import_module("gui.main_window")
    return main_window._load_legacy_module().MotorCalculatorApp


def _live_app_class():
    """The class actually instantiated at runtime (mixin + legacy base)."""

    main_window = importlib.import_module("gui.main_window")
    return main_window._get_real_app_class()


def _legacy_warnings(result):
    """Call the *legacy base* design check without constructing any Tk widget."""

    return _legacy_base_app_class()._check_design_validity(object(), result)


class _StubApp:
    """Minimal stand-in exposing only what the modern design check needs."""

    def __init__(self, parsed_params):
        self._parsed_params = parsed_params
        self._latest_feasibility_assessment = None

    def _get_params(self):
        return self._parsed_params


def _live_warnings(parsed_params, result):
    """Call the design check that the running application actually resolves."""

    return _live_app_class()._check_design_validity(_StubApp(parsed_params), result)


def _evaluate(overrides=None):
    raw = build_sample_legacy_params(**(overrides or {}))
    parsed = parse_legacy_gui_params(raw)
    result = LegacyGuiMotorModelBridge(parsed).run_full_analysis()
    return parsed, result, evaluate_design_feasibility(parsed, result)


def _application_default_inputs():
    from motor_calculator.input_ux.metadata import APPLICATION_DEFAULTS

    return dict(APPLICATION_DEFAULTS)


def _poor_slot_design():
    """A slotted design whose bare-copper occupancy is genuinely too high."""

    return {
        "coreless": False,
        "slot_type": "半闭口槽",
        "slots": 24,
        "h_slot": 15.0,
        "w_slot_top": 8.0,
        "w_slot_bottom": 6.0,
        "h_wedge": 2.0,
        "N_ph_turns": 60,
        "n_parallel": 5,
        "d_wire": 1.2,
    }


# ---------------------------------------------------------------------------
# P0-1 : legacy K_fill is not a slot fill factor and must not claim
#        manufacturability.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label",
    ["application_default", "manufacturability_start", "poor_slot_design"],
)
def test_legacy_k_fill_is_never_a_bounded_fill_ratio(label):
    """A physical fill factor lives in (0, 1]. Legacy K_fill does not."""

    if label == "application_default":
        raw = _application_default_inputs()
    elif label == "manufacturability_start":
        raw = feasible_starting_inputs(_application_default_inputs())
    else:
        raw = dict(_application_default_inputs())
        raw.update(_poor_slot_design())

    parsed = parse_legacy_gui_params(raw)
    result = LegacyGuiMotorModelBridge(parsed).run_full_analysis()
    legacy_k_fill = float(result.performance.fill_factor)

    assert math.isfinite(legacy_k_fill)
    assert legacy_k_fill > 1.0, (
        f"{label}: legacy K_fill={legacy_k_fill:.4f} is expected to exceed 1.0, "
        "which proves it is a linear conductor-width proxy and not a slot "
        "copper-area / slot-area fill factor."
    )


def test_legacy_base_class_manufacturability_warning_is_unconditional():
    """Documents the pre-Phase-8G behaviour that must never come back:
    the legacy base class declares '无法制造' even for a Phase 8G-feasible design."""

    raw = feasible_starting_inputs(_application_default_inputs())
    parsed = parse_legacy_gui_params(raw)
    result = LegacyGuiMotorModelBridge(parsed).run_full_analysis()
    assessment = evaluate_design_feasibility(parsed, result)

    # Phase 8G: slot occupancy is calculable and well inside guidance.
    assert assessment.slot_fill_status is FeasibilityCalculability.APPROXIMATE
    assert assessment.slot_fill_factor is not None
    assert 0.0 < assessment.slot_fill_factor < 0.5
    assert not any(
        issue.code.startswith("SLOT_FILL") and issue.severity is not FeasibilitySeverity.INFO
        for issue in assessment.issues
    )

    # Legacy base class: unconditional manufacturability rejection.
    warnings = _legacy_warnings(result)
    assert any(_claims_unmanufacturable(text) for text in warnings), (
        "legacy base class is expected to emit "
        f"'{LEGACY_MANUFACTURABILITY_TEXT}'. legacy K_fill="
        f"{result.performance.fill_factor:.4f}"
    )


def test_live_application_never_claims_manufacturability_from_legacy_k_fill():
    """Regression lock: the running application must resolve the design check to
    the Phase 8G service, so legacy K_fill can never state '无法制造'."""

    live = _live_app_class()
    assert (
        live._check_design_validity
        is importlib.import_module("gui.main_window").MotorCalculatorAppMixin._check_design_validity
    ), "the modern design check must win the MRO"

    for raw in (
        _application_default_inputs(),
        feasible_starting_inputs(_application_default_inputs()),
    ):
        parsed = parse_legacy_gui_params(raw)
        result = LegacyGuiMotorModelBridge(parsed).run_full_analysis()
        assert float(result.performance.fill_factor) > 1.0  # legacy proxy is huge
        messages = _live_warnings(parsed, result)
        assert not any(_claims_unmanufacturable(text) for text in messages), messages


def test_live_application_never_recommends_more_turns_from_the_legacy_margin():
    raw = feasible_starting_inputs(_application_default_inputs())
    parsed = parse_legacy_gui_params(raw)
    result = LegacyGuiMotorModelBridge(parsed).run_full_analysis()

    assert float(result.performance.voltage_margin_percent) > 40.0  # legacy hint condition
    messages = _live_warnings(parsed, result)
    assert not any(LEGACY_INCREASE_TURNS_TEXT in text for text in messages), messages


def test_phase8g_slot_occupancy_is_bounded_and_independent_of_legacy_k_fill():
    raw = dict(_application_default_inputs())
    raw.update(_poor_slot_design())
    parsed = parse_legacy_gui_params(raw)
    result = LegacyGuiMotorModelBridge(parsed).run_full_analysis()
    assessment = evaluate_design_feasibility(parsed, result)

    assert assessment.slot_fill_factor is not None
    assert 0.0 < assessment.slot_fill_factor
    # The genuinely poor slot design is flagged by the modern layer.
    assert assessment.slot_fill_factor > 0.8
    assert any(issue.code == "SLOT_FILL_SEVERE" for issue in assessment.issues)


def test_legacy_k_fill_ignores_slot_geometry_entirely():
    """Definitive proof that legacy K_fill cannot be a slot fill factor:
    changing the slot cross-section changes the Phase 8G occupancy but leaves
    the legacy proxy bit-identical."""

    base = dict(_application_default_inputs())
    base.update(_poor_slot_design())
    deeper = dict(base)
    deeper["h_slot"] = float(base["h_slot"]) * 2.0

    occupancies = []
    legacy_values = []
    for raw in (base, deeper):
        parsed = parse_legacy_gui_params(raw)
        result = LegacyGuiMotorModelBridge(parsed).run_full_analysis()
        assessment = evaluate_design_feasibility(parsed, result)
        occupancies.append(float(assessment.slot_fill_factor))
        legacy_values.append(float(result.performance.fill_factor))

    assert occupancies[1] < occupancies[0], "slot occupancy must respond to slot depth"
    assert legacy_values[0] == legacy_values[1], (
        "legacy K_fill is expected to be completely insensitive to slot geometry, "
        f"got {legacy_values}"
    )


def test_coreless_geometry_reports_not_enough_geometry_rather_than_legacy_proxy():
    parsed, result, assessment = _evaluate({"coreless": True, "slot_type": "无槽"})

    assert assessment.slot_fill_status is FeasibilityCalculability.NOT_ENOUGH_GEOMETRY
    assert assessment.slot_fill_factor is None
    assert float(result.performance.fill_factor) > 1.0


# ---------------------------------------------------------------------------
# P0-2 : legacy voltage guidance uses a DC-bus basis, not the same-basis
#        SVPWM-compatible line-RMS envelope.
# ---------------------------------------------------------------------------


def test_legacy_voltage_margin_uses_an_optimistic_dc_bus_basis():
    raw = feasible_starting_inputs(_application_default_inputs())
    parsed = parse_legacy_gui_params(raw)
    result = LegacyGuiMotorModelBridge(parsed).run_full_analysis()
    assessment = evaluate_design_feasibility(parsed, result)

    legacy_margin = float(result.performance.voltage_margin_percent)
    same_basis_margin = float(assessment.voltage_margin_percent)

    # Basis check: legacy compares a line-RMS requirement against raw Vdc.
    expected_legacy = (
        (float(parsed["V_dc"]) - float(result.performance.required_voltage_v))
        / float(parsed["V_dc"])
        * 100.0
    )
    assert math.isclose(legacy_margin, expected_legacy, rel_tol=1e-12)

    # Basis check: the modern layer uses the linear SVPWM line-RMS envelope.
    expected_available = float(parsed["V_dc"]) / math.sqrt(2.0)
    assert math.isclose(
        float(assessment.available_voltage_line_rms_v), expected_available, rel_tol=1e-12
    )

    assert legacy_margin > same_basis_margin, (
        "RC1 P0-2 reproduction: the legacy margin is expected to be optimistic. "
        f"legacy={legacy_margin:.4f}% same_basis={same_basis_margin:.4f}%"
    )


def test_legacy_increase_turns_hint_contradicts_the_same_basis_margin():
    """The legacy hint fires while the same-basis headroom is already limited,
    and following the hint reduces the same-basis margin further."""

    raw = feasible_starting_inputs(_application_default_inputs())
    parsed = parse_legacy_gui_params(raw)
    result = LegacyGuiMotorModelBridge(parsed).run_full_analysis()
    assessment = evaluate_design_feasibility(parsed, result)

    warnings = _legacy_warnings(result)
    assert any(LEGACY_INCREASE_TURNS_TEXT in text for text in warnings), (
        "legacy base class is expected to exceed 40% and trigger the increase-turns hint. "
        f"legacy margin={result.performance.voltage_margin_percent:.4f}%"
    )
    assert float(assessment.voltage_margin_percent) < 20.0

    # Following the hint makes the physically meaningful margin worse.
    more_turns = dict(raw)
    more_turns["N_ph_turns"] = int(raw["N_ph_turns"]) + 10
    parsed_more = parse_legacy_gui_params(more_turns)
    result_more = LegacyGuiMotorModelBridge(parsed_more).run_full_analysis()
    assessment_more = evaluate_design_feasibility(parsed_more, result_more)

    assert float(assessment_more.voltage_margin_percent) < float(
        assessment.voltage_margin_percent
    )


def test_legacy_optimizer_voltage_constraint_accepts_a_same_basis_infeasible_candidate():
    """`V_required > V_dc` accepts candidates that exceed the linear SVPWM
    line-RMS envelope `V_dc / sqrt(2)`."""

    raw = feasible_starting_inputs(_application_default_inputs())
    accepted_by_legacy = []
    rejected_by_modern = []

    for turns in range(30, 121, 5):
        candidate = dict(raw)
        candidate["N_ph_turns"] = turns
        parsed = parse_legacy_gui_params(candidate)
        result = LegacyGuiMotorModelBridge(parsed).run_full_analysis()
        assessment = evaluate_design_feasibility(parsed, result)

        required = float(result.performance.required_voltage_v)
        legacy_ok = required <= float(parsed["V_dc"])
        modern_ok = float(assessment.voltage_margin_percent) >= 0.0

        if legacy_ok:
            accepted_by_legacy.append(turns)
        if legacy_ok and not modern_ok:
            rejected_by_modern.append(turns)

    assert accepted_by_legacy
    assert rejected_by_modern, (
        "RC1 P0-2 reproduction: the legacy optimizer constraint is expected to "
        "accept candidates that violate the same-basis SVPWM envelope."
    )
