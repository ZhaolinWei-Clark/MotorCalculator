from __future__ import annotations

from pathlib import Path

import pytest

from calibration_sandbox import (
    SensitivitySandboxError,
    generate_sensitivity_markdown_report,
    run_sensitivity_case,
    run_sensitivity_sweep,
    write_sensitivity_markdown_report,
)
from motor_core.units import legacy_params_to_model_input

from helpers import build_sample_legacy_params


def _baseline_input(turns_per_phase: int = 100):
    params = build_sample_legacy_params(waveform="pmsm_sinusoidal", N_ph_turns=turns_per_phase)
    return legacy_params_to_model_input(params)


def test_run_sensitivity_case_does_not_modify_baseline_input() -> None:
    baseline_input = _baseline_input()
    original_value = baseline_input.remanence_t

    result = run_sensitivity_case(
        baseline_input,
        parameter_name="magnet_remanence_t",
        perturbation_percent=5.0,
    )

    assert result.status == "ok"
    assert baseline_input.remanence_t == original_value
    assert result.perturbation.temporary_value != original_value


def test_perturbation_only_applies_to_copied_input() -> None:
    baseline_input = _baseline_input()
    result = run_sensitivity_case(
        baseline_input,
        parameter_name="air_gap_m",
        perturbation_percent=-1.0,
    )

    assert result.perturbation.internal_field_name == "air_gap_per_side_m"
    assert result.perturbation.baseline_value == baseline_input.air_gap_per_side_m
    assert result.perturbation.temporary_value != baseline_input.air_gap_per_side_m


def test_minus_and_plus_one_percent_produce_recordable_results() -> None:
    baseline_input = _baseline_input()

    minus_result = run_sensitivity_case(
        baseline_input,
        parameter_name="turns_per_phase",
        perturbation_percent=-1.0,
    )
    plus_result = run_sensitivity_case(
        baseline_input,
        parameter_name="turns_per_phase",
        perturbation_percent=1.0,
    )

    assert minus_result.status == "ok"
    assert plus_result.status == "ok"
    assert minus_result.perturbation.temporary_value == 99
    assert plus_result.perturbation.temporary_value == 101
    assert any(change.relative_change_percent is not None for change in minus_result.affected_outputs)
    assert any(change.relative_change_percent is not None for change in plus_result.affected_outputs)


def test_invalid_parameter_name_is_safely_rejected() -> None:
    with pytest.raises(SensitivitySandboxError, match="Unsupported sensitivity parameter"):
        run_sensitivity_case(
            _baseline_input(),
            parameter_name="calibrated_magic_factor",
            perturbation_percent=1.0,
        )


def test_phase_current_target_is_known_but_unavailable_as_production_input() -> None:
    result = run_sensitivity_case(
        _baseline_input(),
        parameter_name="phase_current_a",
        perturbation_percent=1.0,
    )

    assert result.status == "unavailable"
    assert result.perturbation.temporary_value is None
    assert all(change.status == "unavailable" for change in result.affected_outputs)


def test_report_generation_works(tmp_path: Path) -> None:
    summary = run_sensitivity_sweep(
        _baseline_input(),
        parameter_names=["magnet_remanence_t", "phase_current_a"],
        perturbation_percents=(-1.0, 1.0),
    )

    markdown = generate_sensitivity_markdown_report(summary)
    report_path = write_sensitivity_markdown_report(summary, tmp_path / "phase6a_report.md")

    assert "Sandbox boundary statement" in markdown
    assert "phase_current_a" in markdown
    assert report_path.read_text(encoding="utf-8") == markdown
