"""Seeded Monte Carlo propagation for explicitly declared parameter PDFs."""

from __future__ import annotations

import math
import random
import statistics
from collections import Counter
from dataclasses import dataclass

from .uncertainty_models import ParameterUncertainty, UncertaintyKind
from .uncertainty_sweep import MetricEvaluator, PhysicalValidator, _evaluate


@dataclass(frozen=True)
class VarianceAssociationEstimate:
    parameter_name: str
    normalized_r_squared_percent: float
    method: str = "normalized Pearson r-squared association; not a Sobol index"


@dataclass(frozen=True)
class MonteCarloResult:
    random_seed: int
    requested_sample_count: int
    valid_sample_count: int
    failed_sample_count: int
    nominal_result: float
    sample_mean: float
    median: float
    standard_deviation: float
    minimum: float
    maximum: float
    p05: float
    p10: float
    p50: float
    p90: float
    p95: float
    variance_association_estimates: tuple[VarianceAssociationEstimate, ...]
    rejection_reasons: tuple[tuple[str, int], ...]
    warnings: tuple[str, ...]


def _percentile(sorted_values: tuple[float, ...], percentile: float) -> float:
    if not sorted_values:
        raise ValueError("percentiles require at least one value")
    position = (len(sorted_values) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] + fraction * (sorted_values[upper] - sorted_values[lower])


def _sample_parameter(parameter: ParameterUncertainty, rng: random.Random) -> float:
    if parameter.uncertainty_kind is UncertaintyKind.NORMAL:
        return rng.normalvariate(float(parameter.mean), float(parameter.standard_deviation))
    if parameter.uncertainty_kind is UncertaintyKind.UNIFORM:
        return rng.uniform(float(parameter.lower_bound), float(parameter.upper_bound))
    return parameter.nominal_value


def _declared_bound_rejection(
    parameters: tuple[ParameterUncertainty, ...],
    values: dict[str, float],
) -> str | None:
    for parameter in parameters:
        if not parameter.has_parameter_bounds:
            continue
        value = values[parameter.parameter_name]
        if value < float(parameter.lower_bound) or value > float(parameter.upper_bound):
            return f"{parameter.parameter_name}:outside_declared_bounds"
    return None


def _pearson_r_squared(inputs: tuple[float, ...], outputs: tuple[float, ...]) -> float:
    input_mean = statistics.fmean(inputs)
    output_mean = statistics.fmean(outputs)
    numerator = sum(
        (input_value - input_mean) * (output_value - output_mean)
        for input_value, output_value in zip(inputs, outputs)
    )
    input_sum = sum((value - input_mean) ** 2 for value in inputs)
    output_sum = sum((value - output_mean) ** 2 for value in outputs)
    if input_sum == 0.0 or output_sum == 0.0:
        return 0.0
    correlation = numerator / math.sqrt(input_sum * output_sum)
    return correlation * correlation


def _variance_associations(
    parameters: tuple[ParameterUncertainty, ...],
    accepted_inputs: tuple[dict[str, float], ...],
    outputs: tuple[float, ...],
) -> tuple[VarianceAssociationEstimate, ...]:
    raw = {}
    for parameter in parameters:
        if not parameter.statistically_sampleable:
            continue
        values = tuple(sample[parameter.parameter_name] for sample in accepted_inputs)
        raw[parameter.parameter_name] = _pearson_r_squared(values, outputs)
    total = sum(raw.values())
    if total == 0.0:
        return tuple(VarianceAssociationEstimate(name, 0.0) for name in sorted(raw))
    return tuple(
        VarianceAssociationEstimate(name, value / total * 100.0)
        for name, value in sorted(raw.items(), key=lambda item: (-item[1], item[0]))
    )


def run_monte_carlo(
    parameters: tuple[ParameterUncertainty, ...],
    evaluator: MetricEvaluator,
    validator: PhysicalValidator,
    *,
    sample_count: int,
    random_seed: int,
) -> MonteCarloResult:
    if sample_count <= 0:
        raise ValueError("sample_count must be positive")
    nominal_values = {parameter.parameter_name: parameter.nominal_value for parameter in parameters}
    nominal_result, nominal_rejection = _evaluate(nominal_values, evaluator, validator)
    if nominal_rejection is not None or nominal_result is None:
        raise ValueError(f"nominal uncertainty case is invalid: {nominal_rejection}")

    rng = random.Random(random_seed)
    outputs = []
    accepted_inputs = []
    rejection_reasons: Counter[str] = Counter()
    for _ in range(sample_count):
        values = {
            parameter.parameter_name: _sample_parameter(parameter, rng)
            for parameter in parameters
        }
        bound_rejection = _declared_bound_rejection(parameters, values)
        if bound_rejection is not None:
            rejection_reasons[bound_rejection] += 1
            continue
        output, rejection = _evaluate(values, evaluator, validator)
        if output is None:
            rejection_reasons[rejection or "unknown_rejection"] += 1
            continue
        accepted_inputs.append(values)
        outputs.append(output)
    if not outputs:
        raise ValueError("all Monte Carlo samples were rejected")

    sorted_outputs = tuple(sorted(outputs))
    output_tuple = tuple(outputs)
    warnings = [
        "Percentiles describe samples under declared parameter distributions; they are not confidence intervals.",
        "Model-form uncertainty is not included.",
    ]
    range_only = tuple(
        parameter.parameter_name
        for parameter in parameters
        if parameter.uncertainty_kind is UncertaintyKind.RANGE
    )
    unknown = tuple(
        parameter.parameter_name
        for parameter in parameters
        if parameter.uncertainty_kind is UncertaintyKind.UNKNOWN
    )
    if range_only:
        warnings.append(f"RANGE parameters held nominal because no PDF is declared: {', '.join(range_only)}.")
    if unknown:
        warnings.append(f"UNKNOWN parameters held nominal and unsampled: {', '.join(unknown)}.")
    return MonteCarloResult(
        random_seed=random_seed,
        requested_sample_count=sample_count,
        valid_sample_count=len(outputs),
        failed_sample_count=sum(rejection_reasons.values()),
        nominal_result=nominal_result,
        sample_mean=statistics.fmean(outputs),
        median=statistics.median(outputs),
        standard_deviation=statistics.pstdev(outputs),
        minimum=min(outputs),
        maximum=max(outputs),
        p05=_percentile(sorted_outputs, 0.05),
        p10=_percentile(sorted_outputs, 0.10),
        p50=_percentile(sorted_outputs, 0.50),
        p90=_percentile(sorted_outputs, 0.90),
        p95=_percentile(sorted_outputs, 0.95),
        variance_association_estimates=_variance_associations(
            parameters, tuple(accepted_inputs), output_tuple
        ),
        rejection_reasons=tuple(sorted(rejection_reasons.items())),
        warnings=tuple(warnings),
    )
