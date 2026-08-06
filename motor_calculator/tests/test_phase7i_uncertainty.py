from dataclasses import asdict
from pathlib import Path

import pytest

from motor_calculator.validation.afpm_uncertainty import validate_physical_parameter_values
from motor_calculator.validation.fea_reference import load_fea_reference_definition
from motor_calculator.validation.monte_carlo import run_monte_carlo
from motor_calculator.validation.phase7i_uncertainty_report import (
    render_phase7i_report,
    run_phase7i_demonstration,
)
from motor_calculator.validation.uncertainty_models import (
    ModelFormUncertaintyStatus,
    ParameterUncertainty,
    ResultConfidence,
    UncertaintyKind,
    load_uncertainty_specification,
)
from motor_calculator.validation.uncertainty_sweep import (
    BoundSweepMode,
    run_deterministic_parameter_sweep,
    run_parameter_bound_envelope,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = ROOT / "validation_data" / "uncertainty" / "phase7i_afpm_back_emf_uncertainty.json"
REFERENCE_PATH = ROOT / "validation_data" / "fea_reference" / "phase7h_controlled_ssdr_machine.json"


def _parameter(
    name: str,
    kind: UncertaintyKind,
    *,
    nominal: float = 2.0,
    lower: float | None = None,
    upper: float | None = None,
    mean: float | None = None,
    standard_deviation: float | None = None,
) -> ParameterUncertainty:
    return ParameterUncertainty(
        parameter_name=name,
        nominal_value=nominal,
        unit="1",
        uncertainty_kind=kind,
        lower_bound=lower,
        upper_bound=upper,
        mean=mean,
        standard_deviation=standard_deviation,
        provenance="test declaration",
        confidence="test",
        notes=(),
    )


def _always_valid(_values):
    return None


def test_exact_parameter_remains_fixed_in_monte_carlo():
    parameter = _parameter("exact", UncertaintyKind.EXACT)
    result = run_monte_carlo(
        (parameter,), lambda values: values["exact"], _always_valid,
        sample_count=20, random_seed=1,
    )
    assert result.minimum == result.maximum == result.nominal_result == 2.0


def test_normal_sampling_is_deterministic_with_seed():
    parameter = _parameter(
        "normal", UncertaintyKind.NORMAL,
        nominal=2.0, mean=2.0, standard_deviation=0.1,
    )
    first = run_monte_carlo(
        (parameter,), lambda values: values["normal"], _always_valid,
        sample_count=100, random_seed=42,
    )
    second = run_monte_carlo(
        (parameter,), lambda values: values["normal"], _always_valid,
        sample_count=100, random_seed=42,
    )
    assert first == second
    assert first.standard_deviation > 0.0


def test_uniform_sampling_stays_within_explicit_bounds():
    parameter = _parameter(
        "uniform", UncertaintyKind.UNIFORM,
        nominal=2.0, lower=1.5, upper=2.5,
    )
    result = run_monte_carlo(
        (parameter,), lambda values: values["uniform"], _always_valid,
        sample_count=200, random_seed=9,
    )
    assert 1.5 <= result.minimum <= result.maximum <= 2.5


def test_range_is_not_silently_treated_as_uniform():
    parameter = _parameter(
        "range_only", UncertaintyKind.RANGE,
        nominal=2.0, lower=1.0, upper=3.0,
    )
    result = run_monte_carlo(
        (parameter,), lambda values: values["range_only"], _always_valid,
        sample_count=30, random_seed=8,
    )
    assert result.minimum == result.maximum == 2.0
    assert any("RANGE parameters held nominal" in warning for warning in result.warnings)


def test_unknown_is_never_silently_sampled():
    parameter = _parameter("unknown", UncertaintyKind.UNKNOWN)
    result = run_monte_carlo(
        (parameter,), lambda values: values["unknown"], _always_valid,
        sample_count=30, random_seed=8,
    )
    assert result.minimum == result.maximum == 2.0
    assert any("UNKNOWN parameters held nominal" in warning for warning in result.warnings)


def test_percentiles_are_computed_for_valid_samples():
    parameter = _parameter("exact", UncertaintyKind.EXACT, nominal=7.0)
    result = run_monte_carlo(
        (parameter,), lambda values: values["exact"], _always_valid,
        sample_count=12, random_seed=3,
    )
    assert (result.p05, result.p10, result.p50, result.p90, result.p95) == (7.0,) * 5


def test_invalid_physical_samples_are_rejected_without_clamping():
    air_gap = _parameter(
        "air_gap_m", UncertaintyKind.NORMAL,
        nominal=0.001, mean=0.001, standard_deviation=0.01,
    )
    result = run_monte_carlo(
        (air_gap,), lambda values: values["air_gap_m"], validate_physical_parameter_values,
        sample_count=200, random_seed=12,
    )
    assert result.failed_sample_count > 0
    assert result.valid_sample_count + result.failed_sample_count == 200
    assert all(value >= 0.0 for value in (result.minimum, result.maximum))


def test_parameter_bound_envelope_is_deterministic():
    parameters = (
        _parameter("x", UncertaintyKind.RANGE, nominal=2.0, lower=1.0, upper=3.0),
        _parameter("y", UncertaintyKind.UNIFORM, nominal=4.0, lower=3.0, upper=5.0),
    )
    first = run_parameter_bound_envelope(
        parameters, lambda values: values["x"] * values["y"], _always_valid,
        mode=BoundSweepMode.FULL_CORNERS,
    )
    second = run_parameter_bound_envelope(
        parameters, lambda values: values["x"] * values["y"], _always_valid,
        mode=BoundSweepMode.FULL_CORNERS,
    )
    assert first == second
    assert (first.minimum_observed_prediction, first.maximum_observed_prediction) == (3.0, 15.0)


def test_sensitivity_ranking_is_deterministic():
    parameters = (
        _parameter("strong", UncertaintyKind.RANGE, nominal=2.0, lower=1.0, upper=3.0),
        _parameter("weak", UncertaintyKind.RANGE, nominal=4.0, lower=3.9, upper=4.1),
    )
    evaluator = lambda values: 10.0 * values["strong"] + values["weak"]
    first = run_deterministic_parameter_sweep(parameters, evaluator, _always_valid)
    second = run_deterministic_parameter_sweep(parameters, evaluator, _always_valid)
    assert first == second
    assert first.ranked_parameters == ("strong", "weak")


def test_model_form_uncertainty_remains_explicitly_unquantified():
    specification = load_uncertainty_specification(SPEC_PATH)
    assert specification.model_form_uncertainty_status is ModelFormUncertaintyStatus.UNQUANTIFIED


def test_phase7i_demo_is_deterministic_low_confidence_and_does_not_mutate_reference():
    reference = load_fea_reference_definition(REFERENCE_PATH)
    before_object = asdict(reference)
    before_file = REFERENCE_PATH.read_bytes()
    first = run_phase7i_demonstration(ROOT, monte_carlo_sample_count=250, random_seed=77)
    second = run_phase7i_demonstration(ROOT, monte_carlo_sample_count=250, random_seed=77)
    assert first == second
    assert first.accuracy_envelope.confidence_level is ResultConfidence.LOW
    assert first.accuracy_envelope.parameter_bound_min < first.accuracy_envelope.nominal_value
    assert first.accuracy_envelope.parameter_bound_max > first.accuracy_envelope.nominal_value
    assert asdict(reference) == before_object
    assert REFERENCE_PATH.read_bytes() == before_file
    assert render_phase7i_report(first) == render_phase7i_report(second)


def test_committed_phase7i_report_matches_default_demonstration():
    demonstration = run_phase7i_demonstration(ROOT)
    committed_report = (
        ROOT
        / "validation_data"
        / "reports"
        / "phase7i_back_emf_uncertainty_zh.md"
    ).read_text(encoding="utf-8")

    assert committed_report == render_phase7i_report(demonstration)
