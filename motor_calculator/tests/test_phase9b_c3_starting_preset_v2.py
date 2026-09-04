"""Phase 9B Batch C3: candidate starting preset under the corrected voltage basis.

v1 must stay byte-identical and remain the startup default. v2 is a parallel
candidate only; it is promoted with the corrected voltage model, not before.
"""

from __future__ import annotations

import pytest

from motor_core import LegacyGuiMotorModelBridge, parse_legacy_gui_params
from motor_calculator.presets import default_preset_registry
from motor_calculator.validation.design_feasibility import (
    FeasibilitySeverity,
    evaluate_design_feasibility,
)


V1_ID = "design.manufacturability_start.v1"
V2_ID = "design.manufacturability_start.v2"

V1_VALUES = {
    "V_dc": 72.0,
    "P_rated": 600.0,
    "n_rated": 2200.0,
    "d_wire": 1.2,
    "slot_type": "半闭口槽",
    "coreless": False,
}
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

V2_OBSERVED = {
    "rated_torque_nm": 3.183333333333333,
    "current_density_a_per_mm2": 4.209820250627122,
    "slot_occupancy": 0.40028832237874445,
    "legacy_required_voltage_v": 31.331769019079797,
    "corrected_required_voltage_v": 41.09513893395564,
    "legacy_margin_percent": 38.45859350010581,
    "corrected_margin_percent": 19.281523849990723,
    "efficiency_percent": 90.17258508175475,
    "phase_current_rms_a": 14.283583602088006,
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


def test_c3_v1_is_unchanged():
    preset = default_preset_registry().get(V1_ID)

    assert preset.available
    assert dict(preset.values) == V1_VALUES


def test_c3_v2_exists_and_is_loadable():
    preset = default_preset_registry().get(V2_ID)

    assert preset.available
    assert dict(preset.values) == V2_VALUES
    assert "corrected" in preset.provenance.lower()


def test_c3_v2_meets_every_stated_target():
    _parsed, result, assessment = _evaluate(V2_VALUES)

    assert not assessment.has_error
    assert not assessment.has_severe_design_risk
    assert not any(
        issue.severity is FeasibilitySeverity.WARNING for issue in assessment.issues
    )
    assert assessment.current_density_a_per_mm2 <= 5.0
    assert assessment.slot_fill_factor is not None
    assert 0.25 <= assessment.slot_fill_factor <= 0.50  # conservative region
    assert assessment.voltage_margin_percent >= 10.0
    assert result.performance.rated_torque_nm > 0.0
    assert result.performance.efficiency_percent > 0.0


def test_c3_v2_observed_values_are_pinned():
    _parsed, result, assessment = _evaluate(V2_VALUES)
    observed = V2_OBSERVED

    assert result.performance.rated_torque_nm == pytest.approx(
        observed["rated_torque_nm"], rel=1e-12
    )
    assert assessment.current_density_a_per_mm2 == pytest.approx(
        observed["current_density_a_per_mm2"], rel=1e-12
    )
    assert assessment.slot_fill_factor == pytest.approx(observed["slot_occupancy"], rel=1e-12)
    assert result.performance.required_voltage_v == pytest.approx(
        observed["legacy_required_voltage_v"], rel=1e-12
    )
    assert assessment.required_voltage_line_rms_v == pytest.approx(
        observed["corrected_required_voltage_v"], rel=1e-12
    )
    assert assessment.legacy_voltage_margin_percent == pytest.approx(
        observed["legacy_margin_percent"], rel=1e-12
    )
    assert assessment.voltage_margin_percent == pytest.approx(
        observed["corrected_margin_percent"], rel=1e-12
    )
    assert result.performance.efficiency_percent == pytest.approx(
        observed["efficiency_percent"], rel=1e-12
    )


def test_c3_v1_is_infeasible_on_the_corrected_basis_and_v2_is_not():
    """This is exactly why a v2 candidate exists."""

    _p1, _r1, a1 = _evaluate(V1_VALUES)
    _p2, _r2, a2 = _evaluate(V2_VALUES)

    assert a1.legacy_voltage_margin_percent > 0.0  # legacy basis says v1 is fine
    assert a1.voltage_margin_percent < 0.0  # the authoritative basis does not
    assert a2.voltage_margin_percent > 0.0


def test_v2_is_the_startup_default_after_phase9c_promotion():
    """Phase 9C promoted v2; v1 remains available as a legacy reference."""

    import importlib

    mixin = importlib.import_module("gui.main_window").MotorCalculatorAppMixin
    assert mixin.STARTUP_EXAMPLE_PRESET_ID == V2_ID
    assert mixin.LEGACY_STARTUP_EXAMPLE_PRESET_ID == V1_ID
    assert default_preset_registry().get(V1_ID).available


def test_c3_no_validator_was_relaxed_to_admit_v2():
    """The guidance thresholds that v2 satisfies must be the unchanged ones."""

    from motor_calculator.motor_core.constants import DEFAULT_FILL_LIMIT

    assert DEFAULT_FILL_LIMIT == 0.65
    # v2 clears the guidance bands with margin rather than by moving them.
    _parsed, _result, assessment = _evaluate(V2_VALUES)
    assert assessment.current_density_a_per_mm2 < 6.0  # CURRENT_DENSITY_HIGH threshold
    assert assessment.slot_fill_factor < 0.50  # SLOT_FILL_GUIDANCE threshold
