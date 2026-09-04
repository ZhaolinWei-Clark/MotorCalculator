"""Phase 9B Batch C2: optimizer comparison mode.

The legacy optimizer is neither modified nor deleted. This exercises a read-only
replay of its scoring rule against both voltage bases.
"""

from __future__ import annotations

import pytest

from motor_calculator.validation.design_feasibility import (
    feasible_starting_inputs,
    same_basis_available_line_rms_v,
)
from motor_calculator.validation.optimizer_comparison import (
    CORRECTED_VOLTAGE_PATH,
    LEGACY_VOLTAGE_PATH,
    OPTIMIZER_TURNS_RANGE,
    compare_optimizer_paths,
    evaluate_optimizer_path,
    format_optimizer_comparison_zh,
)


def _application_defaults():
    from motor_calculator.input_ux.metadata import APPLICATION_DEFAULTS

    return dict(APPLICATION_DEFAULTS)


def _starting_example():
    return feasible_starting_inputs(_application_defaults())


@pytest.fixture(scope="module")
def comparison():
    return compare_optimizer_paths(_starting_example())


def test_c2_both_paths_use_the_same_inverter_envelope(comparison):
    expected = same_basis_available_line_rms_v(_starting_example()["V_dc"])

    assert comparison.legacy.available_voltage_line_rms_v == pytest.approx(expected)
    assert comparison.corrected.available_voltage_line_rms_v == pytest.approx(expected)


def test_c2_both_paths_evaluate_the_same_candidate_turns(comparison):
    legacy_turns = [item.turns for item in comparison.legacy.candidates]
    corrected_turns = [item.turns for item in comparison.corrected.candidates]

    assert legacy_turns == corrected_turns
    assert set(legacy_turns) <= set(OPTIMIZER_TURNS_RANGE)


def test_c2_corrected_path_accepts_a_strict_subset(comparison):
    legacy_accepted = {item.turns for item in comparison.legacy.accepted}
    corrected_accepted = {item.turns for item in comparison.corrected.accepted}

    assert corrected_accepted < legacy_accepted
    assert comparison.accepted_only_by_corrected == ()
    assert comparison.accepted_only_by_legacy == (48, 51, 54, 57)


def test_c2_ranking_and_recommendation_change(comparison):
    assert comparison.ranking_changed
    assert comparison.recommended_turns_changed
    assert comparison.legacy.best.turns == 51
    assert comparison.corrected.best.turns == 39


def test_c2_corrected_recommendation_is_feasible_on_its_own_basis(comparison):
    best = comparison.corrected.best

    assert best.accepted
    assert best.voltage_margin_percent >= 0.0
    assert best.required_voltage_v <= comparison.corrected.available_voltage_line_rms_v


def test_c2_legacy_recommendation_is_infeasible_on_the_corrected_basis(comparison):
    legacy_turns = comparison.legacy.best.turns
    corrected_entry = next(
        item for item in comparison.corrected.candidates if item.turns == legacy_turns
    )

    assert not corrected_entry.accepted
    assert corrected_entry.voltage_margin_percent < 0.0


def test_c2_every_candidate_reports_the_full_engineering_record(comparison):
    for path in (comparison.legacy, comparison.corrected):
        assert path.candidates
        for item in path.candidates:
            assert item.parallel_paths >= 1
            assert item.required_voltage_v > 0.0
            assert item.current_density_a_per_mm2 > 0.0
            assert item.slot_occupancy is not None  # slotted starting example
            assert item.efficiency_percent > 0.0


def test_c2_paths_are_deterministic():
    first = compare_optimizer_paths(_starting_example())
    second = compare_optimizer_paths(_starting_example())

    assert first.legacy.ranking == second.legacy.ranking
    assert first.corrected.ranking == second.corrected.ranking


def test_c2_unknown_path_is_rejected():
    with pytest.raises(ValueError):
        evaluate_optimizer_path(_starting_example(), "some_other_basis")


def test_c2_report_lines_expose_both_recommendations(comparison):
    text = "\n".join(format_optimizer_comparison_zh(comparison))

    assert LEGACY_VOLTAGE_PATH != CORRECTED_VOLTAGE_PATH
    assert "legacy 推荐" in text
    assert "修正 推荐" in text
    assert "仅 legacy 接受的匝数" in text


def test_c2_legacy_optimizer_source_is_untouched():
    """C2 is comparison only; the legacy method keeps its RC2 behaviour."""

    import importlib
    import inspect

    legacy = importlib.import_module("gui.main_window")._load_legacy_module()
    source = inspect.getsource(legacy.MotorCalculatorApp.run_optimization)

    assert "same_basis_available_line_rms_v" in source  # the RC2 fix is still there
    assert "required_voltage_line_rms_corrected_v" not in source  # no C1 migration yet
